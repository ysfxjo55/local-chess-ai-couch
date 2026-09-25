import { useEffect, useRef, useState } from "react";
import { MessageCircle, RotateCcw } from "lucide-react";
import { useCoachChat } from "@/hooks/useCoachChat";
import { ChatMessageBubble } from "./ChatMessageBubble";
import { ChatComposer } from "./ChatComposer";
import { ToneSwitcher } from "./ToneSwitcher";
import { QuickActionButtons } from "./QuickActionButtons";
import { EmptyState } from "@/components/shared/EmptyState";
import { api } from "@/lib/api";
import type { ChatMessageOut, MoveOut } from "@/lib/apiTypes";
import type { ReplayFrame } from "@/lib/chessReplay";

const NEAR_BOTTOM_THRESHOLD = 80;

interface ChatPanelProps {
  gameId: number | null;
  /** Global chat only. */
  conversationId?: number | null;
  onConversationCreated?: (conversationId: number) => void;
  initialHistory?: ChatMessageOut[];
  currentMove?: MoveOut;
  /** Per-game chat only — the ply currently selected on the board/move
   * list, so the coach is grounded in the real current position. */
  currentPly?: number | null;
  emptyHint?: string;
  /** Only present in the per-game workspace — lets bubbles render an actual
   * board when the coach calls show_position. Omit for the global chat,
   * which has no single game's positions to draw from. */
  frames?: ReplayFrame[];
  orientation?: "white" | "black";
}

/** Shared by the per-game workspace and the global Coach Chat page. Owns
 * only the "start over" reset (remounts the inner panel with a fresh key) —
 * everything conversation-shaped lives in useCoachChat/the calling page. */
export function ChatPanel(props: ChatPanelProps) {
  const [resetKey, setResetKey] = useState(0);

  async function handleStartOver() {
    if (props.gameId === null) return; // global chat resets via the sidebar, not this button
    if (!window.confirm("Start a new conversation for this game? This deletes the current one — it can't be undone.")) {
      return;
    }
    await api.clearGameChat(props.gameId);
    setResetKey((k) => k + 1);
  }

  return (
    <ChatPanelInner
      key={resetKey}
      {...props}
      onStartOver={props.gameId !== null ? handleStartOver : undefined}
    />
  );
}

function ChatPanelInner({
  gameId,
  conversationId,
  onConversationCreated,
  initialHistory = [],
  currentMove,
  currentPly,
  emptyHint = "Ask about this game, or anything about your recent play.",
  frames,
  orientation,
  onStartOver,
}: ChatPanelProps & { onStartOver?: () => void }) {
  const { turns, send, tone, setTone, isStreaming } = useCoachChat({
    gameId,
    conversationId,
    initialHistory,
    onConversationCreated,
    currentPly,
  });
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_THRESHOLD;
    if (nearBottom) el.scrollTop = el.scrollHeight;
  }, [turns]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-slate-border px-3 py-2.5">
        <span className="flex items-center gap-1.5 text-sm font-medium text-ink">
          <MessageCircle className="size-4 text-amber" />
          <span className="hidden sm:inline">Coach</span>
        </span>
        <div className="flex items-center gap-1 sm:gap-2">
          <ToneSwitcher tone={tone} onChange={setTone} />
          {onStartOver && (
            <button
              onClick={onStartOver}
              disabled={isStreaming || turns.length === 0}
              title="Start a new conversation"
              className="flex size-7 items-center justify-center rounded-md text-ink-muted transition-colors hover:bg-slate-surface-raised hover:text-ink disabled:pointer-events-none disabled:opacity-40"
            >
              <RotateCcw className="size-3.5" />
            </button>
          )}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3">
        {turns.length === 0 ? (
          <EmptyState
            icon={<MessageCircle className="size-6" />}
            title="No messages yet"
            description={emptyHint}
          />
        ) : (
          turns.map((turn, i) => (
            <ChatMessageBubble key={i} turn={turn} frames={frames} orientation={orientation} />
          ))
        )}
      </div>

      <div className="space-y-2 border-t border-slate-border p-3">
        <QuickActionButtons
          currentMove={currentMove}
          onSend={send}
          disabled={isStreaming}
        />
        <ChatComposer onSend={send} disabled={isStreaming} showDeepToggle={gameId === null} />
      </div>
    </div>
  );
}
