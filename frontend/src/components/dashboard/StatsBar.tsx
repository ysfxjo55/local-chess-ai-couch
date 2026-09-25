import type { StatsOverview } from "@/lib/apiTypes";
import { Skeleton } from "@/components/ui/skeleton";

function StatTile({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent: string;
}) {
  return (
    <div
      className="rounded-xl border border-slate-border bg-slate-surface p-4 border-l-2"
      style={{ borderLeftColor: accent }}
    >
      <p className="text-xs font-medium text-ink-muted">{label}</p>
      <p className="mt-1.5 text-2xl font-semibold tabular-nums text-ink">
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-ink-muted">{sub}</p>}
    </div>
  );
}

function weightedAvgCpLoss(stats: StatsOverview): number | null {
  const totalGames = stats.accuracy_trend.reduce((sum, p) => sum + p.games, 0);
  if (totalGames === 0) return null;
  const weighted = stats.accuracy_trend.reduce(
    (sum, p) => sum + p.avg_cp_loss * p.games,
    0,
  );
  return Math.round(weighted / totalGames);
}

export function StatsBar({
  stats,
  totalGames,
  isLoading,
}: {
  stats: StatsOverview | undefined;
  totalGames: number | undefined;
  isLoading: boolean;
}) {
  if (isLoading || !stats) {
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-[86px] rounded-xl" />
        ))}
      </div>
    );
  }

  const avgCpLoss = weightedAvgCpLoss(stats);
  const white = Math.round(stats.win_rate_by_color.White * 100);
  const black = Math.round(stats.win_rate_by_color.Black * 100);

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
      <StatTile
        label="Total games"
        value={String(totalGames ?? 0)}
        accent="var(--color-dusty-blue)"
      />
      <StatTile
        label="Win rate"
        value={`${white}% / ${black}%`}
        sub="as White / as Black"
        accent="var(--color-sage)"
      />
      <StatTile
        label="Avg. centipawn loss"
        value={avgCpLoss !== null ? String(avgCpLoss) : "—"}
        sub="lower is better"
        accent="var(--color-amber)"
      />
    </div>
  );
}
