import { useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { AccuracyTrendChart } from "@/components/charts/AccuracyTrendChart";
import { WinRateByColorChart } from "@/components/charts/WinRateByColorChart";
import { WinRateByOpeningChart } from "@/components/charts/WinRateByOpeningChart";
import { BlunderRateByPhaseChart } from "@/components/charts/BlunderRateByPhaseChart";
import { RepertoireDiagnostic } from "@/components/charts/RepertoireDiagnostic";
import { useRepertoire, useStatsOverview } from "@/hooks/useStats";
import { ApiError } from "@/lib/api";
import type { StatsRange } from "@/lib/apiTypes";

const RANGES: { value: StatsRange; label: string }[] = [
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
  { value: "all", label: "All time" },
];

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-border bg-slate-surface p-4">
      <h2 className="mb-3 text-sm font-medium text-ink-muted">{title}</h2>
      {children}
    </div>
  );
}

export default function Insights() {
  const [range, setRange] = useState<StatsRange>("30d");
  const stats = useStatsOverview(range);
  const repertoire = useRepertoire(range);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-ink">Insights</h1>
          <p className="text-sm text-ink-muted">Trends across your games</p>
        </div>
        <Tabs value={range} onValueChange={(v) => setRange(v as StatsRange)}>
          <TabsList>
            {RANGES.map((r) => (
              <TabsTrigger key={r.value} value={r.value}>
                {r.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {stats.isLoading && (
        <div className="grid gap-4 md:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-64 rounded-xl" />
          ))}
        </div>
      )}

      {stats.isError && (
        <ErrorBanner
          message={
            stats.error instanceof ApiError
              ? stats.error.message
              : "Could not load stats."
          }
          onRetry={() => stats.refetch()}
        />
      )}

      {stats.data && (
        <div className="grid gap-4 md:grid-cols-2">
          <ChartCard title="Accuracy trend (avg. centipawn loss, lower is better)">
            <AccuracyTrendChart data={stats.data.accuracy_trend} />
          </ChartCard>
          <ChartCard title="Win rate by color">
            <WinRateByColorChart data={stats.data.win_rate_by_color} />
          </ChartCard>
          <ChartCard title="Win rate by opening">
            <WinRateByOpeningChart data={stats.data.win_rate_by_opening} />
          </ChartCard>
          <ChartCard title="Blunder rate by phase">
            <BlunderRateByPhaseChart data={stats.data.blunder_rate_by_phase} />
          </ChartCard>
        </div>
      )}

      {repertoire.isLoading && <Skeleton className="h-64 rounded-xl" />}
      {repertoire.data && (
        <ChartCard title="Repertoire diagnostic — opening/color combos worth reviewing, weakest first">
          <RepertoireDiagnostic data={repertoire.data.entries} />
        </ChartCard>
      )}
    </div>
  );
}
