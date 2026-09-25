import { useEffect, useRef } from "react";
import { Chessground } from "@lichess-org/chessground";
import type { Api } from "@lichess-org/chessground/api";
import type { Config } from "@lichess-org/chessground/config";
import type { Dests, Key } from "@lichess-org/chessground/types";

export interface BoardArrow {
  orig: Key;
  dest: Key;
  color?: "green" | "blue" | "red" | "yellow";
}

interface ChessgroundBoardProps {
  fen: string;
  orientation: "white" | "black";
  lastMove?: [string, string];
  arrows?: BoardArrow[];
  viewOnly?: boolean;
  turnColor?: "white" | "black";
  legalDests?: Dests;
  /** Unrestricted editing: any piece, either color, to any square — no
   * turn order, no legality. Used for the main game board's "grab any
   * piece and see what happens" exploration, as opposed to the strict,
   * legal-moves-only `!viewOnly` mode (still available, currently unused,
   * kept in case a rules-constrained sandbox is wanted again later). */
  freeMode?: boolean;
  onUserMove?: (orig: Key, dest: Key) => void;
  className?: string;
}

/**
 * Thin hand-rolled wrapper around @lichess-org/chessground — no community
 * React wrapper is used (both existing ones on npm are abandoned since 2022
 * and pinned to ancient chessground majors). Fully controlled: chessground
 * itself holds no independent "current move" state, every prop change is
 * pushed into it via `.set()` (its own diffing update, not a remount).
 */
export function ChessgroundBoard({
  fen,
  orientation,
  lastMove,
  arrows = [],
  viewOnly = true,
  turnColor,
  legalDests,
  freeMode = false,
  onUserMove,
  className,
}: ChessgroundBoardProps) {
  const el = useRef<HTMLDivElement>(null);
  const api = useRef<Api | null>(null);

  function buildConfig(): Config {
    return {
      fen,
      orientation,
      // Deliberately never chessground's own `viewOnly` — that disables DOM
      // event binding once at construction, and a later `.set()` toggling
      // it does NOT rebind those listeners (this board is constructed once
      // read-only, then needs to become interactive when practice starts,
      // without a remount). "Read-only" is instead enforced purely through
      // `movable.color`/`dests` below, which `.set()` genuinely does handle
      // dynamically — same pattern lichess's own analysis board uses.
      viewOnly: false,
      turnColor,
      lastMove: lastMove as Key[] | undefined,
      movable: freeMode
        ? {
            free: true,
            color: "both",
            dests: undefined,
            events: {
              after: (orig, dest) => onUserMove?.(orig, dest),
            },
          }
        : viewOnly
          ? { free: false, color: undefined, dests: undefined }
          : {
              free: false,
              color: turnColor,
              dests: legalDests,
              events: {
                after: (orig, dest) => onUserMove?.(orig, dest),
              },
            },
      drawable: {
        autoShapes: arrows.map((a) => ({
          orig: a.orig,
          dest: a.dest,
          brush: a.color ?? "green",
        })),
      },
      animation: { enabled: true, duration: 200 },
      highlight: { lastMove: true, check: true },
    };
  }

  // Mount once.
  useEffect(() => {
    if (!el.current) return;
    api.current = Chessground(el.current, buildConfig());
    return () => {
      api.current?.destroy();
      api.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Push every relevant change into the existing instance.
  useEffect(() => {
    api.current?.set(buildConfig());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    fen,
    orientation,
    viewOnly,
    turnColor,
    lastMove?.join(","),
    JSON.stringify(arrows),
    legalDests,
    freeMode,
  ]);

  return (
    <div
      ref={el}
      className={className ?? "aspect-square w-full max-w-[560px]"}
    />
  );
}
