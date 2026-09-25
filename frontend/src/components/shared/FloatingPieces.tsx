import { useMemo, type CSSProperties } from "react";

const GLYPHS = ["♔", "♕", "♖", "♗", "♘", "♙", "♚", "♛", "♜", "♝", "♞", "♟"];

// The same calm accent family used sparingly elsewhere (charts, stat
// tiles) — kept consistent so the login screen doesn't introduce a color
// language the rest of the app doesn't share.
const COLORS = [
  "var(--color-amber)",
  "var(--color-dusty-blue)",
  "var(--color-sage)",
  "var(--color-mauve)",
  "var(--color-lavender)",
  "var(--color-teal)",
];

interface Piece {
  id: number;
  glyph: string;
  color: string;
  left: number;
  size: number;
  duration: number;
  delay: number;
  drift: number;
  opacity: number;
}

function generatePieces(count: number): Piece[] {
  const pieces: Piece[] = [];
  for (let i = 0; i < count; i++) {
    // Spread evenly across the width first, then jitter — avoids the
    // clumping a fully random left% would produce with few pieces.
    const slot = (100 / count) * i;
    pieces.push({
      id: i,
      glyph: GLYPHS[Math.floor(Math.random() * GLYPHS.length)],
      color: COLORS[i % COLORS.length],
      left: slot + (Math.random() * 6 - 3),
      size: 24 + Math.random() * 34,
      duration: 22 + Math.random() * 16,
      delay: Math.random() * -35, // negative = staggered start, already mid-flight on mount
      drift: Math.random() * 60 - 30,
      opacity: 0.1 + Math.random() * 0.1,
    });
  }
  return pieces;
}

/**
 * Ambient background for the login screen — chess pieces drifting slowly
 * downward in the calm accent palette. Purely decorative: aria-hidden,
 * pointer-events disabled, and fully removed under prefers-reduced-motion
 * (see the .animate-float-piece media query in index.css).
 */
export function FloatingPieces({ count = 16 }: { count?: number }) {
  const pieces = useMemo(() => generatePieces(count), [count]);

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      {pieces.map((p) => (
        <span
          key={p.id}
          className="animate-float-piece absolute top-0 select-none leading-none"
          style={
            {
              left: `${p.left}%`,
              fontSize: `${p.size}px`,
              color: p.color,
              animationDuration: `${p.duration}s`,
              animationDelay: `${p.delay}s`,
              "--drift": `${p.drift}px`,
              "--piece-opacity": p.opacity,
            } as CSSProperties
          }
        >
          {p.glyph}
        </span>
      ))}
    </div>
  );
}
