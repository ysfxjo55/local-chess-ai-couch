import { ClassificationChip } from "@/components/board/ClassificationChip";
import type { MoveOut } from "@/lib/apiTypes";

/** Small summary of the currently-viewed ply, shown above the chat. */
export function ContextCard({ move }: { move: MoveOut | undefined }) {
  if (!move) {
    return (
      <div className="rounded-lg border border-slate-border bg-slate-surface p-3 text-sm text-ink-muted">
        Viewing the start position.
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between gap-2 rounded-lg border border-slate-border bg-slate-surface p-3 text-sm">
      <div>
        <p className="text-xs text-ink-muted">{move.label}</p>
        <p className="font-medium text-ink">{move.san}</p>
      </div>
      <div className="flex items-center gap-2">
        {move.classification && (
          <ClassificationChip classification={move.classification} />
        )}
        {move.best_move && move.best_move !== move.san && (
          <span className="text-xs text-ink-muted">Best: {move.best_move}</span>
        )}
      </div>
    </div>
  );
}
