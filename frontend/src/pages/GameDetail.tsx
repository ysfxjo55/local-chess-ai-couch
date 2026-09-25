import { useMemo, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, RotateCcw, Check } from "lucide-react";
import type { Key } from "@lichess-org/chessground/types";
import { Chess } from "chess.js";
import { useGame } from "@/hooks/useGames";
import { useMovePointer } from "@/hooks/useMovePointer";
import { ChessgroundBoard } from "@/components/board/ChessgroundBoard";
import { EvalBar } from "@/components/board/EvalBar";
import { MoveStepper } from "@/components/board/MoveStepper";
import { MoveList } from "@/components/board/MoveList";
import { ClassificationChip } from "@/components/board/ClassificationChip";
import { EvalOverTimeChart } from "@/components/charts/EvalOverTimeChart";
import { ResultBadge } from "@/components/dashboard/ResultBadge";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { ContextCard } from "@/components/coach/ContextCard";
import { GameAnalysisPanel } from "@/components/coach/GameAnalysisPanel";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { FloatingChatWidget } from "@/components/chat/FloatingChatWidget";
import { api, ApiError } from "@/lib/api";
import { forkForPractice, bestMoveSquares } from "@/lib/chessReplay";
import { cn } from "@/lib/utils";
import type { BoardArrow } from "@/components/board/ChessgroundBoard";

export default function GameDetail() {
  const { id } = useParams<{ id: string }>();
  const gameId = Number(id);
  const game = useGame(gameId);

  if (game.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-48" />
        <div className="grid gap-4 md:grid-cols-[1fr_340px]">
          <Skeleton className="aspect-square w-full max-w-[560px]" />
          <Skeleton className="h-96" />
        </div>
      </div>
    );
  }

  if (game.isError || !game.data) {
    return (
      <ErrorBanner
        message={
          game.error instanceof ApiError
            ? game.error.message
            : "Could not load this game."
        }
        onRetry={() => game.refetch()}
      />
    );
  }

  return <GameDetailLoaded game={game.data} />;
}

function GameDetailLoaded({ game }: { game: NonNullable<ReturnType<typeof useGame>["data"]> }) {
  const { ply, setPly, frames, fen, lastMove, currentMove, arrow, evalCp, maxPly } =
    useMovePointer(game.moves);
  const [coachOpen, setCoachOpen] = useState(false);
  // The board is always interactive — no separate "enter practice mode"
  // step. While NOT diverged, its FEN is just `fen` from useMovePointer
  // (synchronous, driven directly by `ply` — same as the plain viewer
  // always used). `divergedChessRef` only comes into play the moment a
  // piece is actually dropped; it's a plain ref (not state) since chess.js
  // mutates in place and re-renders are already triggered explicitly via
  // `forceRender`/`divergedFromPly` — an earlier version stored this in
  // state and re-derived it from `ply` inside a useEffect, which meant the
  // board rendered with the PREVIOUS ply's position for one extra frame
  // after every navigation (state set in an effect always lags the render
  // that triggered it) — that was the "board is one move behind" bug.
  const divergedChessRef = useRef<Chess | null>(null);
  const [divergedFromPly, setDivergedFromPly] = useState<number | null>(null);
  const [, forceRender] = useState(0);
  // Which flagged moves' suggested fix you've found — seeded from the
  // server's persisted puzzle_correct (solved via this page or the
  // dedicated Puzzles queue, either counts) and extended locally as you
  // fix more in this session, without waiting for a refetch.
  const [fixedPlies, setFixedPlies] = useState<Set<number>>(
    () => new Set(game.moves.map((m, i) => (m.puzzle_correct ? i : -1)).filter((i) => i >= 0)),
  );

  const orientation = game.player_color.toLowerCase() as "white" | "black";
  const diverged = divergedFromPly !== null;
  const arrows: BoardArrow[] =
    !diverged && arrow ? [{ orig: arrow.orig, dest: arrow.dest, color: "green" }] : [];

  const flaggedMoves = useMemo(
    () =>
      game.moves
        .map((m, i) => ({ move: m, ply: i }))
        .filter(
          ({ move }) =>
            move.is_player_move &&
            (move.classification === "Blunder" || move.classification === "Mistake"),
        ),
    [game.moves],
  );

  /** Any explicit navigation drops whatever hypothetical line was being
   * explored, synchronously (same tick as the ply change) — no effect, no
   * lag, so the board never renders a stale position even for one frame. */
  function goToPly(newPly: number) {
    divergedChessRef.current = null;
    setDivergedFromPly(null);
    setPly(newPly);
  }

  function resetToRealPosition() {
    divergedChessRef.current = null;
    setDivergedFromPly(null);
  }

  function handleBoardMove(orig: Key, dest: Key) {
    // Fully free placement — any piece, either color, any square, no
    // legality or turn-order check. `.move()` would reject exactly the
    // kind of "what if" setups this is for (moving the opponent's piece,
    // two moves in a row, etc.), so this bypasses it entirely and edits
    // the position directly.
    if (orig === dest) return;
    if (!divergedChessRef.current) {
      divergedChessRef.current = forkForPractice(frames, ply);
    }
    const chess = divergedChessRef.current;
    const piece = chess.get(orig as Parameters<Chess["get"]>[0]);
    if (!piece) return;
    chess.remove(orig as Parameters<Chess["remove"]>[0]);
    chess.remove(dest as Parameters<Chess["remove"]>[0]);
    chess.put(piece, dest as Parameters<Chess["put"]>[1]);

    if (divergedFromPly === null) {
      setDivergedFromPly(ply); // triggers the re-render that shows the new (diverged) position
      // The first move away from the real position is the "did you find
      // the fix" moment — only meaningful right when you start diverging,
      // compared against this move's suggested improvement (if flagged).
      const bestMove = game.moves[ply]?.best_move;
      const baseFen = frames[ply]?.fenBefore;
      if (bestMove && baseFen) {
        const squares = bestMoveSquares(baseFen, bestMove);
        if (squares && squares.from === orig && squares.to === dest) {
          setFixedPlies((prev) => new Set(prev).add(ply));
          // Fire-and-forget: keeps this in sync with the dedicated Puzzles
          // queue, which reads the same puzzle_correct flag server-side.
          api.attemptPuzzle({ game_id: game.id, ply, correct: true }).catch(() => {});
        }
      }
    } else {
      forceRender((n) => n + 1); // already diverged — divergedFromPly won't change, force the re-render explicitly
    }
  }

  const boardFen = divergedChessRef.current ? divergedChessRef.current.fen() : fen;
  const boardTurnColor = boardFen.split(" ")[1] === "w" ? "white" : "black";

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link
          to="/"
          className="flex size-8 items-center justify-center rounded-md text-ink-muted hover:bg-slate-surface hover:text-ink"
        >
          <ArrowLeft className="size-4" />
        </Link>
        <div>
          <h1 className="flex items-center gap-2 text-base font-semibold text-ink">
            {game.player} vs {game.opponent}
            <ResultBadge outcome={game.player_outcome} />
          </h1>
          <p className="text-xs text-ink-muted">
            {game.player_color}
            {game.time_class && ` · ${game.time_class[0].toUpperCase()}${game.time_class.slice(1)}`}
            {" · "}
            {game.opening ?? "—"} · {game.date}
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-[1fr_340px]">
        <div className="flex flex-col items-center gap-3">
          <div className="flex w-full max-w-[560px] items-stretch gap-2">
            <EvalBar evalCp={evalCp} />
            <ChessgroundBoard
              fen={boardFen}
              orientation={orientation}
              lastMove={diverged ? undefined : lastMove}
              arrows={arrows}
              freeMode
              turnColor={boardTurnColor}
              onUserMove={handleBoardMove}
            />
          </div>

          <MoveStepper ply={ply} maxPly={maxPly} onChange={goToPly} />

          {diverged && (
            <div className="flex w-full max-w-[560px] items-center justify-between gap-2 rounded-lg border border-amber/30 bg-amber/5 px-3 py-2">
              <p className="text-xs text-ink-muted">
                Exploring from {game.moves[divergedFromPly!]?.label ?? "the start"} — moves here
                don't affect your saved game.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={resetToRealPosition}
                className="shrink-0 gap-1.5"
              >
                <RotateCcw className="size-3.5" />
                Reset
              </Button>
            </div>
          )}

          <div className="w-full max-w-[560px]">
            <EvalOverTimeChart
              moves={game.moves}
              currentPly={ply}
              onSelectPly={goToPly}
            />
          </div>
        </div>

        <div className="flex min-h-0 flex-col gap-3">
          <ContextCard move={currentMove} />

          <GameAnalysisPanel gameId={game.id} analysis={game.coach_analysis} />

          {flaggedMoves.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-ink-muted">Practice a mistake</p>
                <p className="text-xs font-medium text-amber">
                  {fixedPlies.size} / {flaggedMoves.length} fixed
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {flaggedMoves.map(({ move, ply: p }) => {
                  const isFixed = fixedPlies.has(p);
                  return (
                    <button
                      key={p}
                      onClick={() => goToPly(p)}
                      title={isFixed ? `Fixed — revisit ${move.label}` : `Jump to ${move.label}`}
                      className={cn(
                        "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
                        isFixed
                          ? "border-good/40 bg-good/10 text-good"
                          : "border-slate-border text-ink-muted hover:border-amber/40 hover:text-ink",
                      )}
                    >
                      {isFixed && <Check className="size-3" />}
                      {move.label}
                      <ClassificationChip classification={move.classification} />
                    </button>
                  );
                })}
              </div>
              <Button asChild size="sm" className="mt-1 w-full">
                <Link to={`/puzzles?game=${game.id}`}>Learn from your mistakes →</Link>
              </Button>
            </div>
          )}

          <MoveList moves={game.moves} currentPly={ply} onSelect={goToPly} />
        </div>
      </div>

      {/* The coach lives in a floating, draggable/resizable widget — not an
          always-visible inline panel — so the board stays reachable behind
          it instead of being replaced. */}
      <FloatingChatWidget open={coachOpen} onOpenChange={setCoachOpen} title="Coach">
        <ChatPanel
          gameId={game.id}
          initialHistory={game.chat_history}
          currentMove={currentMove}
          currentPly={ply}
          emptyHint="Ask about the current move, or anything else about this game."
          frames={frames}
          orientation={orientation}
        />
      </FloatingChatWidget>
    </div>
  );
}
