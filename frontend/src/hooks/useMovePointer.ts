import { useMemo, useState } from "react";
import type { MoveOut } from "@/lib/apiTypes";
import {
  buildReplay,
  fenAtPly,
  lastMoveAtPly,
  resolveBestMoveArrow,
} from "@/lib/chessReplay";

/**
 * Owns the single "which ply are we viewing" pointer for a game, plus every
 * value derived from it (FEN, last-move highlight, best-move arrow). This
 * is what keeps the board, eval bar, eval chart, and move list trivially in
 * sync — they all read from the same source.
 */
export function useMovePointer(moves: MoveOut[]) {
  const [ply, setPly] = useState(-1); // -1 = start position

  const frames = useMemo(() => buildReplay(moves), [moves]);

  const fen = fenAtPly(frames, ply);
  const lastMove = ply >= 0 ? lastMoveAtPly(frames, ply) : undefined;
  const currentMove = ply >= 0 ? moves[ply] : undefined;
  const arrow =
    ply >= 0
      ? resolveBestMoveArrow(frames, ply, moves[ply]?.best_move ?? null)
      : null;
  const evalCp = currentMove ? currentMove.eval_after : 0;
  const maxPly = moves.length - 1;

  return { ply, setPly, frames, fen, lastMove, currentMove, arrow, evalCp, maxPly };
}
