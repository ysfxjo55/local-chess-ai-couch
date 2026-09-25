import { cn } from "@/lib/utils";
import type { Classification } from "@/lib/apiTypes";

const STYLES: Record<NonNullable<Classification>, string> = {
  Blunder: "bg-blunder/15 text-blunder",
  Mistake: "bg-mistake/15 text-mistake",
  Inaccuracy: "bg-inaccuracy/15 text-inaccuracy",
  Good: "bg-good/15 text-good",
  Excellent: "bg-excellent/15 text-excellent",
};

export function ClassificationChip({
  classification,
  className,
}: {
  classification: Classification;
  className?: string;
}) {
  if (!classification) return null;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium leading-none",
        STYLES[classification],
        className,
      )}
    >
      {classification}
    </span>
  );
}
