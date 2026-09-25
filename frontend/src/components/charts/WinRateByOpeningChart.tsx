import type { OpeningStat } from "@/lib/apiTypes";
import { EmptyState } from "@/components/shared/EmptyState";

// Cycled per row so a list of several openings reads as distinct at a
// glance, instead of one long stack of identical amber bars.
const BAR_COLORS = [
  "var(--color-amber)",
  "var(--color-dusty-blue)",
  "var(--color-sage)",
  "var(--color-mauve)",
  "var(--color-lavender)",
  "var(--color-teal)",
];

export function WinRateByOpeningChart({ data }: { data: OpeningStat[] }) {
  if (data.length === 0) {
    return <EmptyState title="No games in this range" />;
  }

  return (
    <div className="space-y-3">
      {data.map((row, i) => {
        const pct = Math.round(row.win_rate * 100);
        return (
          <div key={row.opening}>
            <div className="mb-1 flex items-center justify-between gap-2 text-sm">
              <span className="truncate text-ink">{row.opening}</span>
              <span className="shrink-0 tabular-nums text-ink-muted">
                {pct}% · {row.games} game{row.games !== 1 && "s"}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-surface-raised">
              <div
                className="h-full rounded-full transition-[width] duration-500"
                style={{
                  width: `${pct}%`,
                  backgroundColor: BAR_COLORS[i % BAR_COLORS.length],
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
