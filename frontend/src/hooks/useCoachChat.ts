import { useEffect, useRef, useState } from "react";
import { streamChat, type ShowPositionEvent } from "@/lib/sse";
import { applyTonePrefix, stripTonePrefix, type Tone } from "@/lib/toneprompt";
import type { ChatMessageOut } from "@/lib/apiTypes";

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  /** Positions the coach chose to show inline, in the order it showed them.
   * Only ever populated in the per-game chat — see coach_llm.py's
   * show_position tool, which has no meaning without one specific game. */
  showPositions?: ShowPositionEvent[];
  /** True on a user turn sent with the "Deep analysis" toggle on, and on
   * the assistant turn replying to it (set once the backend confirms it
   * actually started the deep query, via the `deep` SSE marker frame). */
  deep?: boolean;
  /** True on the assistant turn replying to the silent game-intro message —
   * lets the bubble show "Your game is being analyzed…" instead of a bare
   * cursor while it waits, and never renders a user bubble for the prompt
   * that triggered it. */
  intro?: boolean;
}

const TONE_STORAGE_KEY = "cc_tone";

/** The message that silently kicks off a per-game chat the first time it's
 * opened (empty history) — sent as a real message so the model has
 * something to respond to, but never rendered as a visible user bubble
 * (see the `silent` param on `send`, and the hydration filter below). */
export const GAME_INTRO_PROMPT =
  "Introduce yourself and give me your opening take on this game — reference how it fits my overall patterns and mistakes, not just this game in isolation.";

interface UseCoachChatOptions {
  gameId: number | null;
  /** Global chat only — which conversation this thread belongs to. null
   * means "not created yet," and the backend assigns one on first send. */
  conversationId?: number | null;
  initialHistory?: ChatMessageOut[];
  /** Global chat only — fires once, the moment a brand-new conversation's
   * id comes back from the first message's stream. */
  onConversationCreated?: (conversationId: number) => void;
  /** Per-game chat only — the ply currently selected in the board/move-list
   * UI, sent with every message so the coach is grounded in the real
   * current position instead of guessing it from memory. */
  currentPly?: number | null;
}

/**
 * Shared streaming-chat state machine for both the per-game workspace and
 * the global Coach Chat page. `gameId: null` means the global chat, which
 * additionally threads a `conversationId` through every request.
 */
export function useCoachChat({
  gameId,
  conversationId = null,
  initialHistory = [],
  onConversationCreated,
  currentPly = null,
}: UseCoachChatOptions) {
  const [turns, setTurns] = useState<ChatTurn[]>(() =>
    initialHistory
      // The silent intro prompt is real, persisted history — but it was
      // never meant to be seen as a user message, on this load or any
      // later one, so it's filtered out here too, not just at send time.
      .filter((m) => !(m.role === "user" && m.content === GAME_INTRO_PROMPT))
      .map((m) => ({
        role: m.role,
        // Hydrated history is the only place a tone-prefixed instruction can
        // leak in, since the backend persists whatever it received verbatim —
        // messages generated during the live session are already clean.
        content: m.role === "user" ? stripTonePrefix(m.content) : m.content,
      })),
  );
  const [tone, setToneState] = useState<Tone>(() => {
    const stored = localStorage.getItem(TONE_STORAGE_KEY);
    return stored === "analytical" || stored === "direct" || stored === "patient"
      ? stored
      : "analytical";
  });
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  // Mutable mirror of conversationId — a brand-new conversation's id arrives
  // mid-stream (before the request resolves), so state alone would lag by
  // one render when a second message follows immediately. Seeded once from
  // the prop on mount ONLY — the global chat deliberately keeps the prop
  // pinned at null even after a conversation is created (updating it would
  // remount this component and abort whatever's still streaming), so
  // re-syncing from the prop on every render — as this used to do — wiped
  // out the real id moments after `onConversationCreated` set it below,
  // forcing every single message to start a brand-new conversation instead
  // of continuing the one already open.
  const conversationIdRef = useRef(conversationId);

  useEffect(() => () => abortRef.current?.abort(), []);

  // First time a per-game chat is opened (no history yet), it starts
  // itself — no need to type anything to get the coach's opening take.
  const autoStartedRef = useRef(false);
  useEffect(() => {
    if (gameId !== null && initialHistory.length === 0 && !autoStartedRef.current) {
      autoStartedRef.current = true;
      send(GAME_INTRO_PROMPT, false, true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function setTone(next: Tone) {
    setToneState(next);
    localStorage.setItem(TONE_STORAGE_KEY, next);
  }

  async function send(cleanMessage: string, deep = false, silent = false) {
    if (!cleanMessage.trim() || isStreaming) return;

    setTurns((prev) => [
      ...prev,
      ...(silent ? [] : [{ role: "user" as const, content: cleanMessage, deep }]),
      { role: "assistant", content: "", streaming: true, intro: silent },
    ]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;
    // The silent intro isn't "the user's" message stylistically — it's a
    // system-initiated kickoff, so it skips the tone prefix too.
    const outgoing = silent ? cleanMessage : applyTonePrefix(tone, cleanMessage);

    try {
      await streamChat(
        {
          game_id: gameId,
          conversation_id: gameId === null ? conversationIdRef.current : undefined,
          message: outgoing,
          deep,
          current_ply: gameId !== null ? currentPly : undefined,
        },
        (chunk) => {
          setTurns((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.streaming) next[next.length - 1] = { ...last, content: last.content + chunk };
            return next;
          });
        },
        () => {
          setTurns((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.streaming) next[next.length - 1] = { ...last, streaming: false };
            return next;
          });
          setIsStreaming(false);
        },
        controller.signal,
        (position) => {
          setTurns((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.streaming) {
              next[next.length - 1] = {
                ...last,
                showPositions: [...(last.showPositions ?? []), position],
              };
            }
            return next;
          });
        },
        (newConversationId) => {
          conversationIdRef.current = newConversationId;
          onConversationCreated?.(newConversationId);
        },
        () => {
          setTurns((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.streaming) next[next.length - 1] = { ...last, deep: true };
            return next;
          });
        },
      );
    } catch {
      setTurns((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.streaming) {
          next[next.length - 1] = {
            ...last,
            content: last.content || "Something went wrong generating a reply.",
            streaming: false,
          };
        }
        return next;
      });
      setIsStreaming(false);
    }
  }

  return { turns, send, tone, setTone, isStreaming };
}
