import { cn } from "@/lib/utils";
import type { PlayerOutcome } from "@/lib/apiTypes";

const STYLES: Record<PlayerOutcome, string> = {
  Win: "bg-good/15 text-good border-good/30",
  Loss: "bg-blunder/15 text-blunder border-blunder/30",
  Draw: "bg-ink-muted/15 text-ink-muted border-ink-muted/30",
  Unknown: "bg-ink-muted/15 text-ink-muted border-ink-muted/30",
};

export function ResultBadge({ outcome }: { outcome: PlayerOutcome }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        STYLES[outcome],
      )}
    >
      {outcome}
    </span>
  );
}
