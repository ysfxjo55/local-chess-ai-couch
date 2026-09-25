import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Chess } from "chess.js";
import type { Square } from "chess.js";
import type { Key } from "@lichess-org/chessground/types";
import { Swords, Target, TriangleAlert, Undo2, CheckCircle2 } from "lucide-react";
import { ChessgroundBoard } from "@/components/board/ChessgroundBoard";
import { ClassificationChip } from "@/components/board/ClassificationChip";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { api, ApiError } from "@/lib/api";
import type { PlayerColor, SparringStartResponse, SparringWarning } from "@/lib/apiTypes";
import { legalDests } from "@/lib/chessReplay";
import { cn } from "@/lib/utils";

function fenAfterSans(sans: string[]): string {
  const chess = new Chess();
  for (const san of sans) {
    if (!chess.move(san)) break;
  }
  return chess.fen();
}

const LEVEL_TIERS = [
  { label: "Casual", range: [1100, 1300] as const },
  { label: "Club Player", range: [1400, 1600] as const, recommended: true },
  { label: "Advanced", range: [1700, 1900] as const },
];

export default function Sparring() {
  const levelsQuery = useQuery({ queryKey: ["sparring", "levels"], queryFn: () => api.sparringLevels() });
  const targetQuery = useQuery({
    queryKey: ["sparring", "target-preview"],
    queryFn: () => api.sparringTargetPreview(),
  });

  const [session, setSession] = useState<SparringStartResponse | null>(null);
  const [maiaLevel, setMaiaLevel] = useState<number | null>(null);
  const [targetWeakOpening, setTargetWeakOpening] = useState(true);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const level = maiaLevel ?? levelsQuery.data?.levels[Math.floor((levelsQuery.data?.levels.length ?? 1) / 2)] ?? 1500;

  async function handleStart() {
    setStarting(true);
    setStartError(null);
    try {
      const started = await api.sparringStart({ maia_level: level, target_weak_opening: targetWeakOpening });
      setSession(started);
    } catch (err) {
      setStartError(err instanceof ApiError ? err.message : "Could not start a sparring session.");
    } finally {
      setStarting(false);
    }
  }

  function handleAbandonToSetup() {
    if (session) api.sparringAbandon(session.session_id).catch(() => {});
    setSession(null);
  }

  if (session) {
    return <SparringBoard session={session} onLeave={handleAbandonToSetup} />;
  }

  const target = targetQuery.data;
  const drilling = !!target && targetWeakOpening;
  // Always show a real board — the drilled position when targeting, the
  // start position for free play — rather than an empty placeholder box.
  const previewFen = drilling ? fenAfterSans(target.seed_moves) : new Chess().fen();
  const previewOrientation = (drilling ? target.player_color.toLowerCase() : "white") as
    | "white"
    | "black";

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="flex items-center gap-2.5 text-2xl font-semibold text-ink">
          <Swords className="size-6" />
          Sparring
        </h1>
        <p className="mt-1 text-base text-ink-muted">
          Play live against Maia, a human-like engine, and drill your actual weak spots.
        </p>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_420px]">
        <div className="space-y-3">
          <div className="flex justify-center">
            <ChessgroundBoard
              fen={previewFen}
              orientation={previewOrientation}
              viewOnly
              className="aspect-square w-full max-w-[640px]"
            />
          </div>
          <p className="text-center text-sm text-ink-muted">
            {drilling ? (
              <>
                The game starts here:{" "}
                <span className="font-mono text-ink">{target.seed_moves.join(" ")}</span>
              </>
            ) : (
              "Free play from the starting position"
            )}
          </p>
        </div>

        <div className="space-y-6 rounded-xl border border-slate-border bg-slate-surface p-6">
          {targetQuery.isLoading && <Skeleton className="h-28 rounded-lg" />}

          {target && (
            <div
              className={cn(
                "rounded-xl border p-5 transition-colors",
                targetWeakOpening
                  ? "border-amber/50 bg-linear-to-br from-amber/15 to-transparent"
                  : "border-slate-border",
              )}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-amber">
                  <Target className="size-4" />
                  Targeted practice
                </div>
                <button
                  role="switch"
                  aria-checked={targetWeakOpening}
                  aria-label="Drill your weakest matchup"
                  onClick={() => setTargetWeakOpening((v) => !v)}
                  className={cn(
                    "inline-flex h-7 w-12 shrink-0 items-center rounded-full p-1 transition-colors",
                    targetWeakOpening ? "bg-amber" : "bg-slate-surface-raised",
                  )}
                >
                  <span
                    className={cn(
                      "size-5 rounded-full bg-ink shadow transition-transform",
                      targetWeakOpening ? "translate-x-5" : "translate-x-0",
                    )}
                  />
                </button>
              </div>
              <p className="mt-3 text-lg font-semibold text-ink">
                {target.opening} as {target.player_color}
              </p>
              <span className="mt-2 inline-flex items-center rounded-full border border-blunder/30 bg-blunder/15 px-3 py-1 text-sm font-medium text-blunder">
                {Math.round(target.win_rate * 100)}% win rate · {target.games} games
              </span>
              <p className="mt-3 text-sm text-ink-muted">
                {targetWeakOpening
                  ? "Your weakest opening — the game will be steered into it."
                  : "Off — this session will be free play."}
              </p>
            </div>
          )}

          {!targetQuery.isLoading && !target && (
            <p className="rounded-lg border border-slate-border bg-slate-surface-raised px-4 py-3 text-sm text-ink-muted">
              Not enough repeated-opening data yet to target a weakness — this will be free play.
            </p>
          )}

          <div className="space-y-4">
            <p className="text-base font-semibold text-ink">Maia's strength</p>
            {levelsQuery.isLoading ? (
              <Skeleton className="h-32 w-full rounded-md" />
            ) : (
              LEVEL_TIERS.map((tier) => {
                const tierLevels = (levelsQuery.data?.levels ?? []).filter(
                  (lvl) => lvl >= tier.range[0] && lvl <= tier.range[1],
                );
                if (tierLevels.length === 0) return null;
                return (
                  <div key={tier.label} className="space-y-2">
                    <p className="flex items-center gap-2 text-sm text-ink-muted">
                      {tier.label}
                      {tier.recommended && (
                        <span className="rounded-full bg-amber/15 px-2 py-0.5 text-xs font-medium text-amber">
                          Recommended
                        </span>
                      )}
                    </p>
                    <div className="grid grid-cols-3 gap-2">
                      {tierLevels.map((lvl) => (
                        <button
                          key={lvl}
                          onClick={() => setMaiaLevel(lvl)}
                          className={cn(
                            "h-11 rounded-lg border text-base font-medium tabular-nums transition-all",
                            level === lvl
                              ? "border-amber bg-amber text-obsidian ring-2 ring-amber/30"
                              : "border-slate-border text-ink-muted hover:border-amber/50 hover:text-ink",
                          )}
                        >
                          {lvl}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {startError && <ErrorBanner message={startError} />}

          <Button
            className="h-12 w-full gap-2 text-base transition-transform hover:scale-[1.01]"
            onClick={handleStart}
            disabled={starting || levelsQuery.isLoading || (levelsQuery.data?.levels.length ?? 0) === 0}
          >
            <Swords className="size-5" />
            {starting ? "Starting…" : `Start sparring vs Maia ${level}`}
          </Button>
        </div>
      </div>
    </div>
  );
}

function SparringBoard({
  session,
  onLeave,
}: {
  session: SparringStartResponse;
  onLeave: () => void;
}) {
  const [fen, setFen] = useState(session.fen);
  const [moves, setMoves] = useState(session.moves);
  const [lastMove, setLastMove] = useState<[string, string] | undefined>(undefined);
  const [warning, setWarning] = useState<SparringWarning | null>(null);
  const [done, setDone] = useState(session.done);
  const [result, setResult] = useState<string | null>(null);
  const [gameId, setGameId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const orientation = session.player_color.toLowerCase() as "white" | "black";
  const boardTurnColor = fen.split(" ")[1] === "w" ? "white" : "black";
  const interactive = !done && !warning && !submitting && boardTurnColor === orientation;
  const dests = useMemo(() => (interactive ? legalDests(new Chess(fen)) : undefined), [interactive, fen]);

  async function handleMove(orig: Key, dest: Key) {
    if (!interactive) return;

    const local = new Chess(fen);
    const promotion = local
      .moves({ square: orig as Square, verbose: true })
      .find((m) => m.to === dest)?.promotion;
    const played = local.move({ from: orig, to: dest, promotion });
    if (!played) return;

    // Optimistic: show your move the instant you drop it. Without this the
    // board is still controlled by the pre-move fen for the whole server
    // round trip, so the piece visibly snapped back to its origin and then
    // both moves jumped in at once when the reply arrived.
    const prevFen = fen;
    const afterPlayerFen = local.fen();
    setFen(afterPlayerFen);
    setLastMove([orig, dest]);
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.sparringMove(session.session_id, {
        from_square: orig,
        to_square: dest,
        promotion,
      });
      if (res.maia_san) {
        const reply = new Chess(afterPlayerFen).move(res.maia_san);
        if (reply) setLastMove([reply.from, reply.to]);
      }
      setFen(res.fen);
      setMoves((prev) => [...prev, res.player_san, ...(res.maia_san ? [res.maia_san] : [])]);
      setWarning(res.warning);
      setDone(res.done);
      setResult(res.result);
      setGameId(res.game_id);
    } catch (err) {
      setFen(prevFen);
      setLastMove(undefined);
      setError(err instanceof ApiError ? err.message : "Move failed — try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleTakeback() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.sparringTakeback(session.session_id);
      setFen(res.fen);
      setMoves(res.moves);
      setWarning(null);
      setLastMove(undefined);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not take back.");
    } finally {
      setSubmitting(false);
    }
  }

  function handleContinue() {
    setWarning(null);
  }

  const resultLabel = resultToOutcome(result, session.player_color);

  const status = done
    ? null
    : submitting
      ? "Maia is thinking…"
      : warning
        ? "Review your move"
        : boardTurnColor === orientation
          ? "Your move"
          : null;

  const movePairs: [string, string | undefined][] = [];
  for (let i = 0; i < moves.length; i += 2) movePairs.push([moves[i], moves[i + 1]]);

  return (
    <div className="mx-auto grid max-w-6xl items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="flex justify-center">
        <ChessgroundBoard
          fen={fen}
          orientation={orientation}
          turnColor={boardTurnColor}
          legalDests={dests}
          viewOnly={!interactive}
          lastMove={lastMove}
          onUserMove={handleMove}
          className="aspect-square w-full max-w-[680px]"
        />
      </div>

      <aside className="flex flex-col gap-4">
        <div className="rounded-xl border border-slate-border bg-slate-surface p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold text-ink">vs Maia {session.maia_level}</h1>
              <p className="mt-1 text-sm text-ink-muted">
                You play {session.player_color}
                {session.target && ` · drilling ${session.target.opening}`}
              </p>
            </div>
            <Button variant="outline" onClick={onLeave} disabled={submitting}>
              {done ? "New game" : "Abandon"}
            </Button>
          </div>
          {status && (
            <p className="mt-4 flex items-center gap-2 text-sm font-medium text-ink">
              <span
                className={cn(
                  "size-2 rounded-full",
                  submitting ? "animate-pulse bg-ink-muted" : warning ? "bg-blunder" : "bg-good",
                )}
              />
              {status}
            </p>
          )}
        </div>

        {error && <ErrorBanner message={error} />}

        {warning && (
          <div className="space-y-3 rounded-xl border border-blunder/30 bg-blunder/10 p-5">
            <div className="flex items-start gap-3">
              <TriangleAlert className="mt-0.5 size-5 shrink-0 text-blunder" />
              <div className="min-w-0 text-sm">
                <p className="flex items-center gap-2 font-medium text-ink">
                  <ClassificationChip classification={warning.classification} />
                  lost {warning.cp_loss}cp
                </p>
                {warning.matched_rule && (
                  <p className="mt-2 text-ink-muted">
                    Matches a lesson from a past loss: "{warning.matched_rule}"
                  </p>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="outline" onClick={handleTakeback} disabled={submitting} className="gap-1.5">
                <Undo2 className="size-4" />
                Take back
              </Button>
              <Button onClick={handleContinue} disabled={submitting}>
                Continue
              </Button>
            </div>
          </div>
        )}

        {done && (
          <div className="flex items-start gap-3 rounded-xl border border-amber/30 bg-amber/5 p-5">
            <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-amber" />
            <div className="text-sm">
              <p className="text-base font-semibold text-ink">Game over — {resultLabel}</p>
              {gameId != null ? (
                <p className="mt-1 text-ink-muted">
                  Saved to your games.{" "}
                  <Link to={`/games/${gameId}`} className="font-medium text-amber hover:underline">
                    View full analysis
                  </Link>
                </p>
              ) : (
                <p className="mt-1 text-ink-muted">Draw — nothing to analyze.</p>
              )}
            </div>
          </div>
        )}

        <div className="rounded-xl border border-slate-border bg-slate-surface p-5">
          <p className="mb-3 text-sm font-medium text-ink-muted">Moves</p>
          {movePairs.length === 0 ? (
            <p className="text-sm text-ink-muted">No moves yet.</p>
          ) : (
            <div className="grid max-h-80 grid-cols-[2.5rem_1fr_1fr] gap-x-2 gap-y-1 overflow-y-auto font-mono text-sm">
              {movePairs.map(([w, b], i) => (
                <div key={i} className="contents">
                  <span className="text-ink-muted">{i + 1}.</span>
                  <span className="text-ink">{w}</span>
                  <span className="text-ink">{b ?? ""}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

function resultToOutcome(result: string | null, playerColor: PlayerColor): string {
  if (!result) return "";
  if (result === "1/2-1/2") return "Draw";
  const winner = result === "1-0" ? "White" : "Black";
  return winner === playerColor ? "You won" : "You lost";
}
