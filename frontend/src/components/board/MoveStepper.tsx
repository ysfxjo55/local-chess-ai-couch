import { useEffect } from "react";
import {
  ChevronsLeft,
  ChevronLeft,
  ChevronRight,
  ChevronsRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface MoveStepperProps {
  ply: number; // -1 = start position, 0..maxPly = after that move
  maxPly: number;
  onChange: (ply: number) => void;
}

export function MoveStepper({ ply, maxPly, onChange }: MoveStepperProps) {
  const atStart = ply <= -1;
  const atEnd = ply >= maxPly;

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);
      if (typing) return;

      if (e.key === "ArrowLeft") {
        e.preventDefault();
        onChange(Math.max(-1, ply - 1));
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        onChange(Math.min(maxPly, ply + 1));
      } else if (e.key === "Home") {
        e.preventDefault();
        onChange(-1);
      } else if (e.key === "End") {
        e.preventDefault();
        onChange(maxPly);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [ply, maxPly, onChange]);

  return (
    <div className="flex items-center justify-center gap-1.5">
      <Button
        variant="outline"
        size="icon"
        className="size-11"
        disabled={atStart}
        onClick={() => onChange(-1)}
        aria-label="First move"
      >
        <ChevronsLeft className="size-4" />
      </Button>
      <Button
        variant="outline"
        size="icon"
        className="size-11"
        disabled={atStart}
        onClick={() => onChange(Math.max(-1, ply - 1))}
        aria-label="Previous move"
      >
        <ChevronLeft className="size-4" />
      </Button>
      <span className="min-w-16 text-center text-sm tabular-nums text-ink-muted">
        {ply + 1} / {maxPly + 1}
      </span>
      <Button
        variant="outline"
        size="icon"
        className="size-11"
        disabled={atEnd}
        onClick={() => onChange(Math.min(maxPly, ply + 1))}
        aria-label="Next move"
      >
        <ChevronRight className="size-4" />
      </Button>
      <Button
        variant="outline"
        size="icon"
        className="size-11"
        disabled={atEnd}
        onClick={() => onChange(maxPly)}
        aria-label="Last move"
      >
        <ChevronsRight className="size-4" />
      </Button>
    </div>
  );
}
