import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Chess } from "chess.js";
import type { Square } from "chess.js";
import type { Key } from "@lichess-org/chessground/types";
import { ArrowLeft, Check, ChevronDown, Flag, Lightbulb, PartyPopper, X } from "lucide-react";
import { useGame } from "@/hooks/useGames";
import {
  useAttemptPuzzle,
  useGuessPuzzle,
  useNextPuzzle,
  usePuzzleGames,
  usePuzzleStats,
} from "@/hooks/usePuzzles";
import { ChessgroundBoard } from "@/components/board/ChessgroundBoard";
import type { BoardArrow } from "@/components/board/ChessgroundBoard";
import { ClassificationChip } from "@/components/board/ClassificationChip";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import type { MoveOut, PuzzleGuessResponse, PuzzleOut } from "@/lib/apiTypes";
import { buildReplay, legalDests, resolveBestMoveArrow } from "@/lib/chessReplay";
import { cn } from "@/lib/utils";

type Result = "correct" | "gaveup" | null;

export default function Puzzles() {
  // `?game=<id>` switches from the shuffled cross-game queue to reviewing
  // one specific game's mistakes in chronological order — Lichess's "learn
  // from your mistakes" on a single game. In the URL so it's linkable from
  // GameDetail and survives a refresh mid-review.
  const [searchParams, setSearchParams] = useSearchParams();
  const gameParam = Number(searchParams.get("game"));
  const gameId = Number.isFinite(gameParam) && gameParam > 0 ? gameParam : undefined;

  const puzzleQuery = useNextPuzzle(gameId);
  const statsQuery = usePuzzleStats();
  const puzzle = puzzleQuery.data;

  // In game mode, load the game from the URL directly — so the header can
  // still show the opponent and progress once every mistake is done and
  // there's no current puzzle left to take the game id from.
  const gameQuery = useGame(gameId ?? puzzle?.game_id ?? NaN);

  function selectGame(id: number | undefined) {
    setSearchParams(id != null ? { game: String(id) } : {});
  }

  if (puzzleQuery.isLoading || statsQuery.isLoading) {
    return (
      <div className="mx-auto max-w-[560px] space-y-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="aspect-square w-full" />
      </div>
    );
  }

  if (puzzleQuery.isError) {
    return (
      <ErrorBanner
        message={
          puzzleQuery.error instanceof ApiError
            ? puzzleQuery.error.message
            : "Could not load a puzzle."
        }
        onRetry={() => puzzleQuery.refetch()}
      />
    );
  }

  const stats = statsQuery.data;

  if (!puzzle) {
    if (gameId != null) {
      return (
        <div className="mx-auto max-w-[560px] space-y-4">
          <EmptyState
            icon={<PartyPopper className="size-8" />}
            title={
              gameQuery.data
                ? `Every mistake vs ${gameQuery.data.opponent} reviewed`
                : "Every mistake in this game reviewed"
            }
            description="Pick another game below, or go back to the mixed queue."
            action={
              <Button variant="outline" onClick={() => selectGame(undefined)}>
                Back to all puzzles
              </Button>
            }
          />
          <GamePicker onSelect={selectGame} defaultOpen />
        </div>
      );
    }
    return (
      <EmptyState
        icon={<PartyPopper className="size-8" />}
        title="All caught up"
        description={
          stats
            ? `You've reviewed every flagged blunder and mistake — ${stats.correct} of ${stats.solved} solved correctly. Sync more games to get new puzzles.`
            : "No flagged blunders or mistakes waiting for review."
        }
        action={
          <Button asChild variant="outline">
            <Link to="/">Back to dashboard</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="mx-auto max-w-[560px] space-y-4">
      {gameId != null ? (
        <GameReviewHeader
          opponent={puzzle.opponent}
          moves={gameQuery.data?.moves}
          currentPly={puzzle.ply}
          onExit={() => selectGame(undefined)}
        />
      ) : (
        <>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-base font-semibold text-ink">Blunder Puzzles</h1>
              <p className="text-xs text-ink-muted">
                vs {puzzle.opponent} · {puzzle.label}
                {puzzle.time_class && ` · ${puzzle.time_class}`}
              </p>
            </div>
            {stats && (
              <p className="text-xs font-medium text-ink-muted">
                {stats.solved} / {stats.total} reviewed
              </p>
            )}
          </div>
          <GamePicker onSelect={selectGame} />
        </>
      )}

      <div className="flex items-center gap-2">
        <ClassificationChip classification={puzzle.classification} />
        {puzzle.cp_loss != null && (
          <span className="text-xs text-ink-muted">-{puzzle.cp_loss}cp</span>
        )}
        {gameId != null ? (
          <span className="text-xs text-ink-muted">{puzzle.label}</span>
        ) : (
          <span className="text-xs text-ink-muted">{puzzle.remaining} left in queue</span>
        )}
      </div>

      {gameQuery.isLoading || !gameQuery.data ? (
        <Skeleton className="aspect-square w-full" />
      ) : (
        // Keyed on puzzle identity: a fresh puzzle should get fresh local
        // state (no answer, no drawn move, explanation dialog reopened),
        // via a clean remount rather than effects reaching back to reset
        // state after the fact. `moves` is the raw array — PuzzleBoard
        // derives both `frames` and `move` from it *and* `puzzle.ply`
        // itself, in one place, rather than receiving them as two
        // separately-computed sibling props that could in principle drift
        // apart from each other across a render.
        <PuzzleBoard
          key={`${puzzle.game_id}:${puzzle.ply}`}
          puzzle={puzzle}
          moves={gameQuery.data.moves}
          nextLabel={gameId != null ? "Next mistake" : "Next puzzle"}
          onNext={() => puzzleQuery.refetch()}
        />
      )}
    </div>
  );
}

const FLAGGED_CLASSES = new Set(["Blunder", "Mistake"]);

/**
 * Lichess-style game review header: who it was against, how many
 * blunders/mistakes the game had, and a row of every one of them in move
 * order — done (solved / gave up), the current one, and what's still ahead.
 */
function GameReviewHeader({
  opponent,
  moves,
  currentPly,
  onExit,
}: {
  opponent: string;
  moves: MoveOut[] | undefined;
  currentPly: number;
  onExit: () => void;
}) {
  const flagged = useMemo(
    () =>
      (moves ?? [])
        .map((m, ply) => ({ m, ply }))
        .filter(({ m }) => m.is_player_move && m.classification && FLAGGED_CLASSES.has(m.classification)),
    [moves],
  );
  const blunders = flagged.filter(({ m }) => m.classification === "Blunder").length;
  const mistakes = flagged.length - blunders;
  const index = flagged.findIndex(({ ply }) => ply === currentPly);

  return (
    <div className="space-y-3 rounded-xl border border-slate-border bg-slate-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <button
            onClick={onExit}
            className="mb-1 flex items-center gap-1 text-xs text-ink-muted hover:text-ink"
          >
            <ArrowLeft className="size-3" />
            All games
          </button>
          <h1 className="text-base font-semibold text-ink">Your game vs {opponent}</h1>
          {moves && (
            <p className="text-xs text-ink-muted">
              <span className="text-blunder">{blunders} blunder{blunders !== 1 && "s"}</span>
              {" · "}
              <span className="text-mistake">{mistakes} mistake{mistakes !== 1 && "s"}</span>
              {" — fix them in order"}
            </p>
          )}
        </div>
        {index >= 0 && (
          <p className="shrink-0 text-xs font-medium text-ink-muted">
            {index + 1} / {flagged.length}
          </p>
        )}
      </div>

      {flagged.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {flagged.map(({ m, ply }) => {
            const isCurrent = ply === currentPly;
            const reviewed = m.puzzle_correct !== null;
            const moveNo = `${Math.floor(ply / 2) + 1}${ply % 2 === 1 ? "..." : "."}`;
            return (
              <span
                key={ply}
                title={m.label}
                className={cn(
                  "flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs tabular-nums",
                  isCurrent && "border-amber bg-amber/15 text-amber",
                  !isCurrent && reviewed && m.puzzle_correct && "border-good/40 bg-good/10 text-good",
                  !isCurrent && reviewed && !m.puzzle_correct && "border-slate-border text-ink-muted line-through",
                  !isCurrent && !reviewed && "border-slate-border text-ink-muted",
                )}
              >
                {!isCurrent && reviewed && m.puzzle_correct && <Check className="size-3" />}
                {moveNo} {m.san}
                {m.classification === "Blunder" ? "??" : "?"}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * Collapsed-by-default list of games that still have unreviewed mistakes,
 * newest first — picking one switches the page into that game's review.
 */
function GamePicker({
  onSelect,
  defaultOpen = false,
}: {
  onSelect: (gameId: number) => void;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [showAll, setShowAll] = useState(false);
  const gamesQuery = usePuzzleGames();
  const games = gamesQuery.data?.games ?? [];
  const visible = showAll ? games : games.slice(0, 6);

  return (
    <div className="rounded-lg border border-slate-border bg-slate-surface">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium text-ink"
      >
        Review one game's mistakes in order
        <ChevronDown className={cn("size-4 text-ink-muted transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-1 border-t border-slate-border p-2">
          {gamesQuery.isLoading && <Skeleton className="h-8 w-full" />}
          {!gamesQuery.isLoading && games.length === 0 && (
            <p className="px-1 py-2 text-xs text-ink-muted">No games with unreviewed mistakes.</p>
          )}
          {visible.map((g) => (
            <button
              key={g.game_id}
              onClick={() => onSelect(g.game_id)}
              className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-surface-raised"
            >
              <span className="min-w-0 truncate text-ink">
                vs {g.opponent}
                <span className="ml-2 text-xs text-ink-muted">
                  {g.played_at &&
                    new Date(g.played_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                  {g.time_class && ` · ${g.time_class}`}
                </span>
              </span>
              <span className="shrink-0 text-xs text-blunder">{g.count} to fix</span>
            </button>
          ))}
          {games.length > 6 && (
            <button
              onClick={() => setShowAll((v) => !v)}
              className="w-full px-2 py-1 text-left text-xs text-amber hover:underline"
            >
              {showAll ? "Show fewer" : `Show all ${games.length} games`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function PuzzleBoard({
  puzzle,
  moves,
  nextLabel,
  onNext,
}: {
  puzzle: PuzzleOut;
  moves: MoveOut[];
  nextLabel: string;
  onNext: () => void;
}) {
  const attempt = useAttemptPuzzle();
  const guessMutation = useGuessPuzzle();

  // Single source of truth for this puzzle's position: both derived here,
  // together, from the same `moves` + `puzzle.ply` — see the comment where
  // this component is rendered for why that matters.
  const frames = useMemo(() => buildReplay(moves), [moves]);
  const move = moves[puzzle.ply];

  // Auto-fetched the moment this puzzle mounts, and shown as a modal before
  // any attempt is made — the whole point is telling you what went wrong
  // FIRST ("you played X here, which allowed Y"), then having you find the
  // fix, not revealing it only after you've already guessed.
  const explainQuery = useQuery({
    queryKey: ["puzzle-explain", puzzle.game_id, puzzle.ply],
    queryFn: () => api.explainPuzzle(puzzle.game_id, puzzle.ply),
  });
  const [explainOpen, setExplainOpen] = useState(true);

  const [result, setResult] = useState<Result>(null);
  const [guess, setGuess] = useState<{ orig: string; dest: string } | null>(null);
  // The board's own optimistic drag would otherwise get snapped back to
  // fenBefore on the next re-render (the board is fully controlled by the
  // `fen` prop) — this holds the post-move position so the piece stays put
  // once you've answered. Stays null for a wrong guess: the board just
  // reverts to fenBefore, like Lichess bouncing a wrong move back.
  const [resultFen, setResultFen] = useState<string | null>(null);
  // Rating of the most recent wrong guess — a hint, not the answer. Cleared
  // implicitly whenever `result` resolves (correct/gave up), since the
  // banner below switches to the final message at that point.
  const [lastGuess, setLastGuess] = useState<PuzzleGuessResponse | null>(null);
  const [attempts, setAttempts] = useState(0);
  const [checking, setChecking] = useState(false);
  // The position with your attempted move on it, held while it's being
  // checked and briefly after a wrong verdict — so the piece stays where you
  // dropped it instead of snapping back the instant you let go, and only
  // slides back once you've seen the rating.
  const [pendingFen, setPendingFen] = useState<string | null>(null);
  const revertTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (revertTimer.current) clearTimeout(revertTimer.current);
  }, []);

  const fenBefore = frames[puzzle.ply]?.fenBefore ?? "start";
  const orientation = puzzle.player_color.toLowerCase() as "white" | "black";
  const dests = useMemo(() => legalDests(new Chess(fenBefore)), [fenBefore]);

  const arrows: BoardArrow[] = useMemo(() => {
    if (result === null || !move.best_move) return [];
    const squares = resolveBestMoveArrow(frames, puzzle.ply, move.best_move);
    return squares ? [{ orig: squares.orig, dest: squares.dest, color: "green" }] : [];
  }, [result, move, frames, puzzle.ply]);

  async function handleMove(orig: Key, dest: Key) {
    if (result !== null || explainOpen || checking || pendingFen) return;

    // chess.js already constrained the drag to a legal destination via
    // `dests` — this just resolves whether THIS specific move needs a
    // promotion piece, since the backend needs the real UCI move.
    const local = new Chess(fenBefore);
    const promotion = local
      .moves({ square: orig as Square, verbose: true })
      .find((m) => m.to === dest)?.promotion;
    const played = local.move({ from: orig, to: dest, promotion });
    const afterFen = played ? local.fen() : null;

    setPendingFen(afterFen);
    setGuess({ orig, dest });
    setChecking(true);
    try {
      const res = await guessMutation.mutateAsync({
        gameId: puzzle.game_id,
        ply: puzzle.ply,
        body: { from_square: orig, to_square: dest, promotion },
      });
      setLastGuess(res);

      if (res.solved) {
        setResultFen(afterFen);
        setPendingFen(null);
        setResult("correct");
        attempt.mutate({ game_id: puzzle.game_id, ply: puzzle.ply, correct: true });
      } else {
        // Leave the wrong move on the board long enough to read the
        // rating, then let chessground animate it back to the start.
        setAttempts((a) => a + 1);
        revertTimer.current = setTimeout(() => {
          setPendingFen(null);
          setGuess(null);
        }, 900);
      }
    } catch {
      setPendingFen(null);
      setGuess(null);
    } finally {
      setChecking(false);
    }
  }

  function handleGiveUp() {
    if (result !== null) return;
    if (move.best_move) {
      const chess = new Chess(fenBefore);
      const moveResult = chess.move(move.best_move);
      if (moveResult) {
        setGuess({ orig: moveResult.from, dest: moveResult.to });
        setResultFen(chess.fen());
      }
    }
    setResult("gaveup");
    attempt.mutate({ game_id: puzzle.game_id, ply: puzzle.ply, correct: false });
  }

  return (
    <>
      <Dialog open={explainOpen} onOpenChange={setExplainOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Lightbulb className="size-4 text-amber" />
              What went wrong
            </DialogTitle>
          </DialogHeader>
          {explainQuery.isLoading && (
            <div className="flex items-center gap-2 py-2 text-sm text-ink-muted">
              <LoadingSpinner className="size-4" />
              Analyzing this moment…
            </div>
          )}
          {explainQuery.isError && (
            <p className="text-sm text-blunder">
              {explainQuery.error instanceof ApiError
                ? explainQuery.error.message
                : "Could not load the explanation."}
            </p>
          )}
          {explainQuery.data && (
            <p className="text-sm leading-relaxed text-ink">{explainQuery.data.explanation}</p>
          )}
          <DialogFooter>
            <Button onClick={() => setExplainOpen(false)}>Got it — let's solve it</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ChessgroundBoard
        fen={resultFen ?? pendingFen ?? fenBefore}
        orientation={orientation}
        turnColor={orientation}
        legalDests={result === null && !explainOpen && !checking && !pendingFen ? dests : undefined}
        viewOnly={result !== null || explainOpen || checking || !!pendingFen}
        arrows={arrows}
        lastMove={guess ? [guess.orig, guess.dest] : undefined}
        onUserMove={handleMove}
      />

      <div
        className={cn(
          "flex min-h-[3rem] items-center gap-2 rounded-lg border px-3 py-2 text-sm",
          result === "correct" && "border-good/30 bg-good/10 text-good",
          result === "gaveup" && "border-slate-border bg-slate-surface text-ink-muted",
          result === null &&
            lastGuess &&
            "border-blunder/30 bg-blunder/10 text-blunder",
          result === null && !lastGuess && "border-slate-border bg-slate-surface text-ink-muted",
        )}
      >
        {checking && (
          <>
            <LoadingSpinner className="size-4 shrink-0" />
            <span>Checking…</span>
          </>
        )}
        {!checking && result === "correct" && (
          <>
            <Check className="size-4 shrink-0" />
            <span>
              {lastGuess?.is_best || lastGuess?.san === move.best_move
                ? `Correct — ${lastGuess?.san} was the best move`
                : `Good — ${lastGuess?.san} works (-${lastGuess?.cp_loss}cp). Best was ${move.best_move}`}
              {attempts > 0 ? ` (took ${attempts + 1} tries)` : ""}.
            </span>
          </>
        )}
        {!checking && result === "gaveup" && (
          <span>Gave up — the best move was {move.best_move}.</span>
        )}
        {!checking && result === null && lastGuess && (
          <>
            <X className="size-4 shrink-0" />
            <span className="flex items-center gap-2">
              <ClassificationChip classification={lastGuess.classification} />
              {lastGuess.san} lost {lastGuess.cp_loss}cp — try again.
            </span>
          </>
        )}
        {!checking && result === null && !lastGuess && (
          <span>Your turn — find the move you missed.</span>
        )}
      </div>

      <div className="flex items-center justify-between gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={handleGiveUp}
          disabled={result !== null}
          className="gap-1.5"
        >
          <Flag className="size-3.5" />
          Give up
        </Button>
        <Button size="sm" onClick={onNext} disabled={result === null}>
          {nextLabel}
        </Button>
      </div>
    </>
  );
}
