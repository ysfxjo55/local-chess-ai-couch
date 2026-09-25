import { Chess } from "chess.js";
import type { Dests, Key } from "@lichess-org/chessground/types";
import type { MoveOut } from "./apiTypes";

export interface ReplayFrame {
  ply: number;
  /** Position before this ply's move was played. */
  fenBefore: string;
  /** Position after this ply's move was played. */
  fenAfter: string;
  /** [from, to] squares of the move that produced fenAfter. */
  lastMoveSquares: [string, string];
}

/**
 * GameDetail never includes FEN/PGN — only an ordered list of SAN moves.
 * This replays that list once through chess.js to reconstruct every
 * position. Pure function, no React — call once per game load and memoize
 * (useMemo keyed on the game id), since every other piece of the page
 * (board, eval bar, eval chart, arrows, practice sandbox) derives from this
 * single array.
 */
export function buildReplay(moves: MoveOut[]): ReplayFrame[] {
  const chess = new Chess();
  const frames: ReplayFrame[] = [];

  moves.forEach((m, ply) => {
    const fenBefore = chess.fen();
    const result = chess.move(m.san);
    if (!result) {
      throw new Error(`chessReplay: illegal SAN "${m.san}" at ply ${ply}`);
    }
    frames.push({
      ply,
      fenBefore,
      fenAfter: chess.fen(),
      lastMoveSquares: [result.from, result.to],
    });
  });

  return frames;
}

export const START_FEN =
  "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

/** FEN to display for a given ply. -1 means "before move 1" (start position). */
export function fenAtPly(frames: ReplayFrame[], ply: number): string {
  if (ply < 0 || !frames[ply]) return START_FEN;
  return frames[ply].fenAfter;
}

export function lastMoveAtPly(
  frames: ReplayFrame[],
  ply: number,
): [string, string] | undefined {
  return frames[ply]?.lastMoveSquares;
}

/**
 * Resolves a move's best_move (a SAN string, from the position *before* that
 * ply was played) into board squares for drawing an arrow. Returns null for
 * moves with no best_move, or defensively if the backend ever sends a
 * malformed SAN that doesn't apply to the position (don't crash the board
 * over a data issue).
 */
export function resolveBestMoveArrow(
  frames: ReplayFrame[],
  ply: number,
  bestMoveSan: string | null,
): { orig: Key; dest: Key } | null {
  if (!bestMoveSan || !frames[ply]) return null;
  try {
    const clone = new Chess(frames[ply].fenBefore);
    const result = clone.move(bestMoveSan);
    if (!result) return null;
    return { orig: result.from as Key, dest: result.to as Key };
  } catch {
    return null;
  }
}

/**
 * Hands back a live, mutable chess.js instance seeded at the position right
 * before the given ply's move was played — used by the "practice this
 * position" sandbox. Entirely local; no backend call involved.
 */
export function forkForPractice(frames: ReplayFrame[], ply: number): Chess {
  const fen = frames[ply]?.fenBefore ?? START_FEN;
  return new Chess(fen);
}

/**
 * Parses a SAN move (e.g. a coach/engine suggestion) against a given
 * position to get its actual from/to squares — needed to compare a
 * dragged move against a suggestion, since free/legal-move drags only
 * hand back squares, not SAN.
 */
export function bestMoveSquares(
  fen: string,
  sanMove: string,
): { from: string; to: string } | null {
  try {
    const result = new Chess(fen).move(sanMove);
    return result ? { from: result.from, to: result.to } : null;
  } catch {
    return null;
  }
}

/**
 * Legal destination squares grouped by origin square, for Chessground's
 * movable.dests. chess.js's square strings structurally satisfy
 * Chessground's `Key` template-literal type — the cast here is safe and
 * kept contained to this one conversion point.
 */
export function legalDests(chess: Chess): Dests {
  const dests: Dests = new Map();
  for (const move of chess.moves({ verbose: true })) {
    const from = move.from as Key;
    const list = dests.get(from) ?? [];
    list.push(move.to as Key);
    dests.set(from, list);
  }
  return dests;
}
