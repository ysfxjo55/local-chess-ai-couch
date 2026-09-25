import { useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw, CheckCircle2, TriangleAlert } from "lucide-react";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerFooter,
  DrawerClose,
  DrawerTrigger,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { useSyncGames } from "@/hooks/useGames";
import { ApiError } from "@/lib/api";

export function SyncDrawer() {
  const [open, setOpen] = useState(false);
  const sync = useSyncGames();

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (next) sync.reset();
  }

  const progress = sync.syncStatus;
  const isRunning = sync.isPending && progress?.status === "running";
  const pct = progress && progress.total > 0
    ? Math.round((progress.processed / progress.total) * 100)
    : 0;

  return (
    <Drawer open={open} onOpenChange={handleOpenChange}>
      <DrawerTrigger asChild>
        <Button className="gap-2">
          <RefreshCw className="size-4" />
          Sync
        </Button>
      </DrawerTrigger>
      <DrawerContent>
        <div className="mx-auto w-full max-w-sm">
          <DrawerHeader>
            <DrawerTitle>Sync from Chess.com</DrawerTitle>
            <DrawerDescription>
              Fetches new games and runs Stockfish analysis on each move.
              First-time syncs pull your full history and can take a while.
            </DrawerDescription>
          </DrawerHeader>

          <div className="px-4 pb-4">
            {isRunning && (
              <div className="flex flex-col items-center gap-3 rounded-lg border border-slate-border bg-slate-surface p-6">
                <div className="size-8 animate-spin rounded-full border-2 border-slate-border border-t-amber" />
                <div className="w-full text-center">
                  <p className="text-sm font-medium text-ink">
                    Analyzing games…
                  </p>
                  <p className="mt-1 text-xs text-ink-muted">
                    {progress.processed} / {progress.total} months fetched
                    {progress.new_games > 0 && ` · ${progress.new_games} new game${progress.new_games !== 1 ? "s" : ""}`}
                  </p>
                </div>
                {progress.total > 0 && (
                  <div className="w-full">
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-surface-raised">
                      <div
                        className="h-full rounded-full bg-amber transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <p className="mt-1 text-right text-[11px] text-ink-muted">{pct}%</p>
                  </div>
                )}
              </div>
            )}

            {sync.error && (
              <ErrorBanner
                message={
                  sync.error instanceof ApiError && sync.error.message === "no_chesscom_username"
                    ? "Add your Chess.com username above first, then sync."
                    : sync.error instanceof ApiError
                      ? sync.error.message
                      : "Could not reach Chess.com or the backend."
                }
                onRetry={() => sync.mutate()}
              />
            )}

            {sync.isSuccess && progress && (
              <div className="flex items-start gap-3 rounded-lg border border-good/30 bg-good/10 p-4">
                <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-good" />
                <div className="text-sm">
                  <p className="font-medium text-ink">
                    {progress.new_games === 0
                      ? "Already up to date"
                      : `${progress.new_games} new game${progress.new_games !== 1 ? "s" : ""} synced`}
                  </p>
                  {progress.games.length > 0 && (
                    <ul className="mt-2 space-y-1 text-ink-muted">
                      {progress.games.map((g) => (
                        <li key={g.id}>
                          vs {g.opponent} · {g.result}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}

            {/* Cheap, deterministic (no LLM) heads-up on what just came in —
                distinct from the slower per-game AI writeup, which is only
                ready once you open a lost game. */}
            {sync.isSuccess && progress && progress.blunders_found > 0 && (
              <div className="mt-3 flex items-start gap-3 rounded-lg border border-blunder/30 bg-blunder/10 p-4">
                <TriangleAlert className="mt-0.5 size-5 shrink-0 text-blunder" />
                <div className="text-sm">
                  <p className="font-medium text-ink">
                    {progress.blunders_found} blunder{progress.blunders_found !== 1 && "s"} in
                    the new games
                  </p>
                  {progress.worst_blunder && (
                    <p className="mt-1 text-ink-muted">
                      Worst: {progress.worst_blunder.san} ({progress.worst_blunder.label}) vs{" "}
                      {progress.worst_blunder.opponent} — lost {progress.worst_blunder.cp_loss}cp.{" "}
                      <Link
                        to={`/games/${progress.worst_blunder.game_id}`}
                        className="font-medium text-amber hover:underline"
                      >
                        View game
                      </Link>
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          <DrawerFooter>
            {!sync.isPending && !sync.isSuccess && (
              <Button onClick={() => sync.mutate()}>Start sync</Button>
            )}
            <DrawerClose asChild>
              <Button variant="outline" disabled={sync.isPending}>
                {sync.isSuccess ? "Done" : "Cancel"}
              </Button>
            </DrawerClose>
          </DrawerFooter>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
