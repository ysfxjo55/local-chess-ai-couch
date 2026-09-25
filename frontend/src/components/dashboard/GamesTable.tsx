import { useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import type { GameListItem } from "@/lib/apiTypes";
import { ResultBadge } from "./ResultBadge";
import { GameRow, MistakeCounts, formatTimeClass } from "./GameRow";
import { EmptyState } from "@/components/shared/EmptyState";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

/**
 * Renders two parallel markup blocks (table vs. stacked cards) toggled
 * purely with `hidden md:table` / `md:hidden`, rather than a JS breakpoint
 * hook — avoids a layout-thrash flash on load, per the plan's mobile
 * responsiveness section.
 */
export function GamesTable({ games }: { games: GameListItem[] }) {
  const navigate = useNavigate();

  if (games.length === 0) {
    return (
      <EmptyState
        title="No games yet"
        description="Sync your Chess.com account to pull in your game history."
      />
    );
  }

  return (
    <>
      <table className="hidden w-full border-separate border-spacing-y-1.5 md:table">
        <thead>
          <tr className="text-left text-xs font-medium text-ink-muted">
            <th className="px-3 pb-1 font-medium">Opponent</th>
            <th className="px-3 pb-1 font-medium">Result</th>
            <th className="px-3 pb-1 font-medium">Opening</th>
            <th className="px-3 pb-1 font-medium">Mistakes</th>
            <th className="px-3 pb-1 font-medium">Date</th>
            <th className="px-3 pb-1 font-medium" />
          </tr>
        </thead>
        <tbody>
          {games.map((game) => (
            <tr
              key={game.id}
              className="group cursor-pointer bg-slate-surface transition-colors hover:bg-slate-surface-raised"
              onClick={() => navigate(`/games/${game.id}`)}
            >
              <td className="rounded-l-lg px-3 py-3 text-sm font-medium text-ink">
                {game.opponent}
                <span className="block text-xs font-normal text-ink-muted">
                  {game.player_color}
                  {formatTimeClass(game.time_class) && ` · ${formatTimeClass(game.time_class)}`}
                </span>
              </td>
              <td className="px-3 py-3">
                <ResultBadge outcome={game.player_outcome} />
              </td>
              <td className="px-3 py-3 text-sm text-ink-muted">
                {game.opening ?? "—"}
              </td>
              <td className="px-3 py-3">
                <MistakeCounts game={game} />
              </td>
              <td className="px-3 py-3 text-sm tabular-nums text-ink-muted">
                {formatDate(game.played_at)}
              </td>
              <td className="rounded-r-lg px-3 py-3">
                <ChevronRight className="size-4 text-ink-muted transition-transform group-hover:translate-x-0.5" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="flex flex-col gap-2 md:hidden">
        {games.map((game) => (
          <GameRow key={game.id} game={game} />
        ))}
      </div>
    </>
  );
}
