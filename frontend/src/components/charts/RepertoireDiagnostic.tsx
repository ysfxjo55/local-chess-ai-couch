import type { RepertoireStat } from "@/lib/apiTypes";
import { EmptyState } from "@/components/shared/EmptyState";
import { cn } from "@/lib/utils";

function winRateColor(rate: number) {
  if (rate < 0.35) return "text-blunder";
  if (rate < 0.55) return "text-mistake";
  return "text-good";
}

/**
 * Same opening name means a different repertoire branch depending which
 * side you're on, so every row is (opening, color) — not just opening.
 * Sorted worst win rate first by the backend: this is a "what to go review"
 * list, not a "what do I play most" chart, so the weak spots lead.
 */
export function RepertoireDiagnostic({ data }: { data: RepertoireStat[] }) {
  if (data.length === 0) {
    return (
      <EmptyState
        title="Not enough repeated openings yet"
        description="Play (or sync) more games — this needs several games in the same opening/color to be meaningful."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-y-1.5 text-sm">
        <thead>
          <tr className="text-left text-xs font-medium text-ink-muted">
            <th className="px-3 pb-1 font-medium">Opening</th>
            <th className="px-3 pb-1 font-medium">Color</th>
            <th className="px-3 pb-1 font-medium">Games</th>
            <th className="px-3 pb-1 font-medium">Win rate</th>
            <th className="px-3 pb-1 font-medium">Opening accuracy</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={`${row.opening}:${row.player_color}`} className="bg-slate-surface">
              <td className="max-w-[220px] truncate rounded-l-lg px-3 py-2.5 text-ink" title={row.opening}>
                {row.opening}
              </td>
              <td className="px-3 py-2.5 text-ink-muted">{row.player_color}</td>
              <td className="px-3 py-2.5 tabular-nums text-ink-muted">{row.games}</td>
              <td className={cn("px-3 py-2.5 tabular-nums font-medium", winRateColor(row.win_rate))}>
                {Math.round(row.win_rate * 100)}%
              </td>
              <td className="rounded-r-lg px-3 py-2.5 tabular-nums text-ink-muted">
                {row.avg_cp_loss_opening != null ? `-${Math.round(row.avg_cp_loss_opening)}cp avg` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
