import type { BlunderRateByPhase } from "@/lib/apiTypes";

const PHASES: { key: keyof BlunderRateByPhase; label: string }[] = [
  { key: "opening", label: "Opening" },
  { key: "middlegame", label: "Middlegame" },
  { key: "endgame", label: "Endgame" },
];

export function BlunderRateByPhaseChart({ data }: { data: BlunderRateByPhase }) {
  const max = Math.max(...PHASES.map((p) => data[p.key]), 0.01);

  return (
    <div className="space-y-4">
      {PHASES.map(({ key, label }) => {
        const rate = data[key];
        const pct = Math.round(rate * 100);
        const widthPct = Math.round((rate / max) * 100);
        return (
          <div key={key}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="text-ink">{label}</span>
              <span className="tabular-nums text-ink-muted">{pct}%</span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-slate-surface-raised">
              <div
                className="h-full rounded-full bg-blunder transition-[width] duration-500"
                style={{ width: `${widthPct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
