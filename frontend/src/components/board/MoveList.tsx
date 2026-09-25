import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { MoveOut } from "@/lib/apiTypes";
import { ClassificationChip } from "./ClassificationChip";

interface MoveListProps {
  moves: MoveOut[];
  currentPly: number; // -1 = start position
  onSelect: (ply: number) => void;
}

function MoveButton({
  move,
  ply,
  active,
  onSelect,
}: {
  move: MoveOut;
  ply: number;
  active: boolean;
  onSelect: (ply: number) => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!active || !ref.current) return;
    // Deliberately not scrollIntoView() — it walks up EVERY scrollable
    // ancestor, including the page itself, so on mobile (where the whole
    // page scrolls and this list sits below the fold) stepping through
    // moves was yanking the entire page down to reveal the list. Scroll
    // only this list's own container instead.
    const container = ref.current.closest<HTMLElement>("[data-move-list-scroll]");
    if (!container) return;
    const el = ref.current;
    const elTop = el.offsetTop;
    const elBottom = elTop + el.offsetHeight;
    const viewTop = container.scrollTop;
    const viewBottom = viewTop + container.clientHeight;
    if (elTop < viewTop) {
      container.scrollTop = elTop;
    } else if (elBottom > viewBottom) {
      container.scrollTop = elBottom - container.clientHeight;
    }
  }, [active]);

  return (
    <button
      ref={ref}
      onClick={() => onSelect(ply)}
      className={cn(
        "flex min-w-0 flex-1 items-center gap-1.5 rounded px-2 py-1.5 text-left text-sm transition-colors",
        active
          ? "bg-amber/15 text-amber"
          : "text-ink hover:bg-slate-surface-raised",
      )}
    >
      <span className="truncate font-medium">{move.san}</span>
      {move.is_player_move && (
        <ClassificationChip classification={move.classification} />
      )}
    </button>
  );
}

/** Standard two-column (White/Black) PGN-style move list, click-to-jump. */
export function MoveList({ moves, currentPly, onSelect }: MoveListProps) {
  const rows: { moveNumber: number; white?: number; black?: number }[] = [];
  moves.forEach((_, ply) => {
    const moveNumber = Math.floor(ply / 2) + 1;
    let row = rows.find((r) => r.moveNumber === moveNumber);
    if (!row) {
      row = { moveNumber };
      rows.push(row);
    }
    if (ply % 2 === 0) row.white = ply;
    else row.black = ply;
  });

  return (
    <div
      data-move-list-scroll
      className="max-h-[360px] overflow-y-auto rounded-lg border border-slate-border bg-slate-surface"
    >
      <button
        onClick={() => onSelect(-1)}
        className={cn(
          "flex w-full items-center px-3 py-1.5 text-left text-xs font-medium",
          currentPly === -1
            ? "bg-amber/15 text-amber"
            : "text-ink-muted hover:bg-slate-surface-raised",
        )}
      >
        Start position
      </button>
      {rows.map((row) => (
        <div key={row.moveNumber} className="flex items-stretch border-t border-slate-border/60">
          <span className="flex w-9 shrink-0 items-center justify-center text-xs tabular-nums text-ink-muted">
            {row.moveNumber}
          </span>
          {row.white !== undefined && (
            <MoveButton
              move={moves[row.white]}
              ply={row.white}
              active={currentPly === row.white}
              onSelect={onSelect}
            />
          )}
          {row.black !== undefined && (
            <MoveButton
              move={moves[row.black]}
              ply={row.black}
              active={currentPly === row.black}
              onSelect={onSelect}
            />
          )}
        </div>
      ))}
    </div>
  );
}
