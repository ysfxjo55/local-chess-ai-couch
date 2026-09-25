import { Link } from "react-router-dom";
import { Lightbulb, X } from "lucide-react";
import { useDeleteRule, useRules } from "@/hooks/useRules";

/**
 * Auto-generated takeaways from lost games (see backend's InsightsRule) —
 * the same list every coach chat gets injected as context, surfaced here so
 * the player can actually see what the coach "remembers" about them, and
 * prune anything that's wrong or no longer relevant. Renders nothing when
 * there's nothing to show yet, rather than an empty card on a fresh account.
 */
export function LessonsCard() {
  const rules = useRules();
  const deleteRule = useDeleteRule();

  if (!rules.data || rules.data.rules.length === 0) return null;

  return (
    <div className="rounded-xl border border-slate-border bg-slate-surface p-4">
      <h2 className="mb-3 flex items-center gap-1.5 text-sm font-medium text-ink-muted">
        <Lightbulb className="size-4" />
        Lessons from your losses
      </h2>
      <ul className="max-h-56 space-y-2 overflow-y-auto pr-1">
        {rules.data.rules.map((rule) => (
          <li
            key={rule.id}
            className="flex items-start justify-between gap-2 rounded-lg bg-slate-surface-raised px-3 py-2 text-sm text-ink"
          >
            <span className="min-w-0">
              {rule.content}
              {rule.game_id != null && (
                <>
                  {" — "}
                  <Link
                    to={`/games/${rule.game_id}`}
                    className="text-amber hover:underline"
                  >
                    view game
                  </Link>
                </>
              )}
            </span>
            <button
              onClick={() => deleteRule.mutate(rule.id)}
              aria-label="Dismiss lesson"
              className="shrink-0 text-ink-muted transition-colors hover:text-ink"
            >
              <X className="size-3.5" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
