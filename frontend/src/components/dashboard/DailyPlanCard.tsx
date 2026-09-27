import { Check, CircleDot, Dumbbell, Puzzle, Swords } from "lucide-react";
import { Link } from "react-router-dom";
import { useCompletePlanItem, useDailyPlan, usePlayerProfile } from "@/hooks/useLearning";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { ApiError } from "@/lib/api";
import type { DailyPlanItem } from "@/lib/apiTypes";

const itemIcon = {
  review: Puzzle,
  new_puzzle: Puzzle,
  focus: Dumbbell,
  sparring: Swords,
} as const;

function destination(item: DailyPlanItem): string | undefined {
  if ((item.kind === "review" || item.kind === "new_puzzle") && item.reference_id) {
    const [game] = item.reference_id.split(":");
    return `/puzzles?game=${game}`;
  }
  if (item.kind === "sparring") return "/sparring";
  return undefined;
}

export function DailyPlanCard() {
  const plan = useDailyPlan();
  const profile = usePlayerProfile();
  const complete = useCompletePlanItem();

  if (plan.isLoading || profile.isLoading) return <Skeleton className="h-64 rounded-xl" />;
  if (plan.isError) {
    const message = plan.error instanceof ApiError ? plan.error.message : "Could not build today’s training plan.";
    return <ErrorBanner message={message} onRetry={() => plan.refetch()} />;
  }
  const data = plan.data;
  if (!data) return null;
  const completed = data.items.filter((item) => item.completed_at).length;

  return (
    <section className="rounded-xl border border-slate-border bg-slate-surface p-5" aria-labelledby="daily-plan-title">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-amber">Personal training</p>
          <h2 id="daily-plan-title" className="mt-1 text-base font-semibold text-ink">Today’s evidence-based plan</h2>
          <p className="mt-1 text-sm text-ink-muted">{completed} of {data.items.length} blocks complete · {data.timezone}</p>
        </div>
        <span className="rounded-full bg-slate-surface-raised px-2.5 py-1 text-xs font-medium text-ink-muted">{data.plan_date}</span>
      </div>

      {profile.data && profile.data.focus_areas.length > 0 && (
        <p className="mt-4 rounded-lg border border-amber/20 bg-amber/5 px-3 py-2 text-sm text-ink-muted">
          <strong className="text-ink">Current focus:</strong> {profile.data.focus_areas[0].skill_key.replace(":", " — ")} based on {profile.data.focus_areas[0].evidence_count} recorded evidence points.
        </p>
      )}

      <ol className="mt-4 space-y-2" aria-label="Daily training plan">
        {data.items.length === 0 && <li className="text-sm text-ink-muted">Sync and analyze games to create your first evidence-backed training plan.</li>}
        {data.items.map((item) => {
          const Icon = itemIcon[item.kind];
          const to = destination(item);
          const busy = complete.isPending && complete.variables === item.id;
          return (
            <li key={item.id} className="flex items-start gap-3 rounded-lg border border-slate-border px-3 py-3">
              <Icon className="mt-0.5 size-4 shrink-0 text-amber" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className={`text-sm font-medium ${item.completed_at ? "text-ink-muted line-through" : "text-ink"}`}>{item.ordinal}. {item.title}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">{item.rationale} · {item.target_minutes} min</p>
              </div>
              <div className="flex shrink-0 gap-1.5">
                {to && <Button asChild variant="outline" size="sm"><Link to={to}>Open</Link></Button>}
                <Button variant="ghost" size="sm" aria-label={`Mark ${item.title} complete`} disabled={Boolean(item.completed_at) || busy} onClick={() => complete.mutate(item.id)}>
                  {item.completed_at ? <Check className="size-4 text-good" /> : <CircleDot className="size-4" />}
                </Button>
              </div>
            </li>
          );
        })}
      </ol>
      {complete.isError && <p role="alert" className="mt-3 text-sm text-blunder">Could not update this plan item. Please try again.</p>}
    </section>
  );
}
