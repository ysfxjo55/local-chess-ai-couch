import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import type { GameListItem } from "@/lib/apiTypes";
import { ResultBadge } from "./ResultBadge";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function formatTimeClass(timeClass: GameListItem["time_class"]) {
  if (!timeClass) return null;
  return timeClass[0].toUpperCase() + timeClass.slice(1);
}

function MistakeCounts({ game }: { game: GameListItem }) {
  return (
    <div className="flex items-center gap-3 text-xs tabular-nums text-ink-muted">
      {game.blunders > 0 && (
        <span className="text-blunder">{game.blunders} blunder{game.blunders !== 1 && "s"}</span>
      )}
      {game.mistakes > 0 && (
        <span className="text-mistake">{game.mistakes} mistake{game.mistakes !== 1 && "s"}</span>
      )}
      {game.inaccuracies > 0 && (
        <span className="text-inaccuracy">{game.inaccuracies} inaccuracy</span>
      )}
      {game.blunders === 0 && game.mistakes === 0 && game.inaccuracies === 0 && (
        <span className="text-good">Clean game</span>
      )}
    </div>
  );
}

/** Card layout used below the `md` breakpoint — see GamesTable's dual-markup strategy. */
export function GameRow({ game }: { game: GameListItem }) {
  return (
    <Link
      to={`/games/${game.id}`}
      className="flex items-center justify-between gap-3 rounded-lg border border-slate-border bg-slate-surface p-4 transition-colors active:bg-slate-surface-raised"
    >
      <div className="min-w-0 space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-ink">
            vs {game.opponent}
          </span>
          <ResultBadge outcome={game.player_outcome} />
        </div>
        <div className="flex items-center gap-2 text-xs text-ink-muted">
          <span>{game.player_color}</span>
          {formatTimeClass(game.time_class) && (
            <>
              <span>·</span>
              <span>{formatTimeClass(game.time_class)}</span>
            </>
          )}
          <span>·</span>
          <span>{game.opening ?? "—"}</span>
          <span>·</span>
          <span className="tabular-nums">{formatDate(game.played_at)}</span>
        </div>
        <MistakeCounts game={game} />
      </div>
      <ChevronRight className="size-4 shrink-0 text-ink-muted" />
    </Link>
  );
}

export { MistakeCounts, formatTimeClass };
