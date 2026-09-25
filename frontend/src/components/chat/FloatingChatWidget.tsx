import { useEffect, useRef, useState, type ReactNode } from "react";
import { MessageCircle, X } from "lucide-react";

const STORAGE_KEY = "cc_chat_widget_rect";
const DEFAULT_WIDTH = 380;
const DEFAULT_HEIGHT = 520;
const MIN_WIDTH = 300;
const MIN_HEIGHT = 320;

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

function loadRect(): Rect | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (
      typeof parsed?.x === "number" &&
      typeof parsed?.y === "number" &&
      typeof parsed?.width === "number" &&
      typeof parsed?.height === "number"
    ) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

function saveRect(rect: Rect) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(rect));
  } catch {
    // Private-browsing/quota errors — position just won't persist, fine.
  }
}

function defaultRect(): Rect {
  const width = DEFAULT_WIDTH;
  const height = Math.min(DEFAULT_HEIGHT, window.innerHeight - 32);
  return {
    x: Math.max(16, window.innerWidth - width - 24),
    y: Math.max(16, window.innerHeight - height - 96),
    width,
    height,
  };
}

function clampRect(rect: Rect): Rect {
  const width = Math.min(Math.max(rect.width, MIN_WIDTH), Math.max(MIN_WIDTH, window.innerWidth - 16));
  const height = Math.min(Math.max(rect.height, MIN_HEIGHT), Math.max(MIN_HEIGHT, window.innerHeight - 16));
  const x = Math.min(Math.max(rect.x, 0), Math.max(0, window.innerWidth - width));
  const y = Math.min(Math.max(rect.y, 0), Math.max(0, window.innerHeight - height));
  return { x, y, width, height };
}

/**
 * A movable, resizable floating panel — not a fixed-position sheet. Drag the
 * header to reposition, drag the corner grip to resize; both persist to
 * localStorage (per-browser, not synced) so the layout you set up sticks
 * around. Opens collapsed to a round trigger button when closed.
 */
export function FloatingChatWidget({
  open,
  onOpenChange,
  title = "Coach",
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  children: ReactNode;
}) {
  const [rect, setRect] = useState<Rect>(() =>
    typeof window === "undefined"
      ? { x: 0, y: 0, width: DEFAULT_WIDTH, height: DEFAULT_HEIGHT }
      : clampRect(loadRect() ?? defaultRect()),
  );
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);
  const resizeRef = useRef<{ startX: number; startY: number; origW: number; origH: number } | null>(null);

  // Keep the widget on-screen if the window itself resizes.
  useEffect(() => {
    function onResize() {
      setRect((r) => clampRect(r));
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    function onPointerMove(e: PointerEvent) {
      if (dragRef.current) {
        const { startX, startY, origX, origY } = dragRef.current;
        setRect((r) => clampRect({ ...r, x: origX + (e.clientX - startX), y: origY + (e.clientY - startY) }));
      } else if (resizeRef.current) {
        const { startX, startY, origW, origH } = resizeRef.current;
        setRect((r) =>
          clampRect({ ...r, width: origW + (e.clientX - startX), height: origH + (e.clientY - startY) }),
        );
      }
    }
    function onPointerUp() {
      if (!dragRef.current && !resizeRef.current) return;
      dragRef.current = null;
      resizeRef.current = null;
      setRect((r) => {
        saveRect(r);
        return r;
      });
    }
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, []);

  function startDrag(e: React.PointerEvent) {
    dragRef.current = { startX: e.clientX, startY: e.clientY, origX: rect.x, origY: rect.y };
  }
  function startResize(e: React.PointerEvent) {
    e.stopPropagation();
    resizeRef.current = { startX: e.clientX, startY: e.clientY, origW: rect.width, origH: rect.height };
  }

  if (!open) {
    return (
      <button
        onClick={() => onOpenChange(true)}
        className="fixed bottom-20 right-4 z-40 flex size-14 items-center justify-center rounded-full bg-amber text-obsidian shadow-lg shadow-black/40 active:scale-95 sm:bottom-6 sm:right-6"
        aria-label="Open coach"
      >
        <MessageCircle className="size-6" />
      </button>
    );
  }

  return (
    <div
      className="fixed z-40 flex flex-col overflow-hidden rounded-2xl border border-slate-border bg-obsidian shadow-2xl shadow-black/50"
      style={{ left: rect.x, top: rect.y, width: rect.width, height: rect.height }}
    >
      <div
        onPointerDown={startDrag}
        className="flex shrink-0 touch-none cursor-move items-center justify-between border-b border-slate-border px-3 py-2 select-none"
      >
        <span className="text-sm font-medium text-ink">{title}</span>
        <button
          onClick={() => onOpenChange(false)}
          aria-label="Close coach"
          className="flex size-7 items-center justify-center rounded-md text-ink-muted hover:bg-slate-surface hover:text-ink"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col">{children}</div>

      <div
        onPointerDown={startResize}
        aria-hidden
        title="Drag to resize"
        className="absolute bottom-0.5 right-0.5 size-4 touch-none cursor-nwse-resize opacity-50 hover:opacity-90"
      >
        <svg viewBox="0 0 16 16" className="size-full text-ink-muted">
          <path
            d="M14 14L2 14M14 14L14 2M14 14L8 14M14 14L14 8"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            fill="none"
          />
        </svg>
      </div>
    </div>
  );
}
