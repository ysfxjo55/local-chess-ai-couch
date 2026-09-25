import type { WinRateByColor } from "@/lib/apiTypes";

function Row({ label, rate, fill }: { label: string; rate: number; fill: string }) {
  const pct = Math.round(rate * 100);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-ink">{label}</span>
        <span className="tabular-nums text-ink-muted">{pct}%</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-slate-surface-raised">
        <div
          className="h-full rounded-full transition-[width] duration-500"
          style={{ width: `${pct}%`, backgroundColor: fill }}
        />
      </div>
    </div>
  );
}

export function WinRateByColorChart({ data }: { data: WinRateByColor }) {
  return (
    <div className="space-y-4">
      <Row label="As White" rate={data.White} fill="#e8e6e1" />
      <Row label="As Black" rate={data.Black} fill="#d4a373" />
    </div>
  );
}
