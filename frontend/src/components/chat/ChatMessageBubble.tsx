import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Microscope, Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { markdownComponents } from "@/components/coach/markdownComponents";
import { StreamingCursor } from "./StreamingCursor";
import { ChessgroundBoard } from "@/components/board/ChessgroundBoard";
import { fenAtPly, lastMoveAtPly, type ReplayFrame } from "@/lib/chessReplay";
import type { ChatTurn } from "@/hooks/useCoachChat";

interface ChatMessageBubbleProps {
  turn: ChatTurn;
  /** Only present in the per-game workspace — see ChatPanel. */
  frames?: ReplayFrame[];
  orientation?: "white" | "black";
}

/** Small read-only board the coach shows inline via the show_position tool —
 * real position data (chessReplay), not the model describing pixels. */
function InlinePosition({
  ply,
  caption,
  frames,
  orientation,
}: {
  ply: number;
  caption?: string;
  frames: ReplayFrame[];
  orientation: "white" | "black";
}) {
  return (
    <div className="mt-2 max-w-[220px] rounded-lg border border-slate-border bg-slate-surface p-2">
      <ChessgroundBoard
        className="aspect-square w-full"
        fen={fenAtPly(frames, ply)}
        orientation={orientation}
        lastMove={lastMoveAtPly(frames, ply)}
        viewOnly
      />
      {caption && <p className="mt-1.5 text-center text-xs text-ink-muted">{caption}</p>}
    </div>
  );
}

/** Explicit copy-to-clipboard — a reliable fallback for whenever native
 * text selection is finicky (long-press gestures inside a custom-styled,
 * sometimes draggable, mobile chat UI are notoriously unreliable). */
function CopyButton({ text, light }: { text: string; light?: boolean }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API unavailable (e.g. non-HTTPS) — nothing more to do.
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label="Copy message"
      className={cn(
        "mt-1.5 flex items-center gap-1 text-[11px] transition-colors",
        light ? "text-obsidian/60 hover:text-obsidian" : "text-ink-muted hover:text-ink",
      )}
    >
      {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

export function ChatMessageBubble({ turn, frames, orientation = "white" }: ChatMessageBubbleProps) {
  const isUser = turn.role === "user";

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-3.5 py-2",
          isUser
            ? "bg-amber text-obsidian"
            : "border border-slate-border bg-slate-surface",
        )}
      >
        {isUser ? (
          <div>
            {turn.deep && (
              <span className="mb-1 flex items-center gap-1 text-[11px] font-medium text-amber">
                <Microscope className="size-3" /> Deep analysis
              </span>
            )}
            <p className="text-sm leading-relaxed whitespace-pre-wrap">
              {turn.content}
            </p>
            {turn.content && <CopyButton text={turn.content} light />}
          </div>
        ) : turn.content ? (
          <div className="prose-chess">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {turn.content}
            </ReactMarkdown>
            {turn.streaming && <StreamingCursor />}
            {!turn.streaming && <CopyButton text={turn.content} />}
          </div>
        ) : turn.deep ? (
          <p className="flex items-center gap-1.5 text-sm text-ink-muted">
            <Microscope className="size-3.5 shrink-0 animate-pulse text-amber" />
            Analyzing your recent games in depth…
          </p>
        ) : turn.intro ? (
          <p className="text-sm text-ink-muted">
            Your game is being analyzed — I'll review it with you based on
            your style, your common mistakes, and how you usually play.
          </p>
        ) : (
          <StreamingCursor />
        )}

        {frames && turn.showPositions?.map((pos, i) => (
          <InlinePosition
            key={i}
            ply={pos.ply}
            caption={pos.caption}
            frames={frames}
            orientation={orientation}
          />
        ))}
      </div>
    </div>
  );
}
