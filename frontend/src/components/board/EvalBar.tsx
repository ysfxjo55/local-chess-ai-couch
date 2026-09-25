const MATE_CP = 10000; // matches backend's MATE_CP exactly (python-chess mate_score convention)
const MATE_THRESHOLD = 9500; // backend's own "is this basically a mate score" cutoff (MATE_CP - 500)

/** Logistic win-probability curve — a common, reasonable way to compress
 * unbounded centipawn values into a 0-100% bar fill without huge swings
 * at the extremes looking identical to smaller-but-still-large ones. */
function cpToWhitePercent(cp: number): number {
  if (cp >= MATE_THRESHOLD) return 100;
  if (cp <= -MATE_THRESHOLD) return 0;
  const winProb = 1 / (1 + Math.pow(10, -cp / 400));
  return winProb * 100;
}

/** python-chess encodes mate distance directly into the score:
 * `MATE_CP - movesToMate` (winning) or `-(MATE_CP - movesToMate)` (losing).
 * Decoding it back gives "Mate in N" instead of a bare "Mate" that looks
 * identical — and looks stuck/buggy — whether it's mate in 1 or mate in 15. */
function formatEvalLabel(cp: number): string {
  if (Math.abs(cp) >= MATE_THRESHOLD) {
    const movesToMate = Math.max(0, MATE_CP - Math.abs(cp));
    return movesToMate === 0 ? "Mate" : `Mate in ${movesToMate}`;
  }
  const pawns = cp / 100;
  return pawns > 0 ? `+${pawns.toFixed(1)}` : pawns.toFixed(1);
}

/**
 * Vertical eval bar — white's advantage grows from the bottom, matching
 * the lichess/chess.com convention. `evalCp` is always from White's
 * perspective (matches the backend's white_cp() convention).
 */
export function EvalBar({ evalCp }: { evalCp: number }) {
  const whitePercent = cpToWhitePercent(evalCp);

  return (
    <div className="flex h-full w-6 flex-col-reverse overflow-hidden rounded-md border border-slate-border bg-obsidian md:w-7">
      {/* Short transition — long enough to feel smooth on a single step,
          short enough not to visibly lag behind the board during rapid
          stepping (300ms was long enough to look like a desync bug). */}
      <div
        className="w-full bg-ink transition-[height] duration-100 ease-out"
        style={{ height: `${whitePercent}%` }}
      />
      <div className="flex flex-1 items-end justify-center pb-1">
        <span className="tabular-nums [writing-mode:vertical-rl] text-[10px] font-medium text-ink-muted">
          {formatEvalLabel(evalCp)}
        </span>
      </div>
    </div>
  );
}
