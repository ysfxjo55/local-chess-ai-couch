import { clearToken, getToken } from "./api";
import type { CoachChatRequest } from "./apiTypes";

// Same cross-origin reasoning as lib/api.ts — "" in dev (proxied), the real
// backend URL in production.
const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export interface ShowPositionEvent {
  ply: number;
  caption?: string;
}

/**
 * Consumes the streaming SSE response from POST /api/coach/chat.
 *
 * Uses fetch + a raw ReadableStream reader rather than EventSource, since
 * this is a POST request with a body — EventSource only supports GET.
 * Framing matches coach.py exactly: `data: {"content": "..."}\n\n` text
 * chunks, an occasional `data: {"showPosition": {...}}\n\n` when the coach
 * calls the show_position tool (per-game chat only), terminated by
 * `data: {"done": true}\n\n`.
 */
export async function streamChat(
  payload: CoachChatRequest,
  onChunk: (content: string) => void,
  onDone: () => void,
  signal?: AbortSignal,
  onShowPosition?: (event: ShowPositionEvent) => void,
  onConversationCreated?: (conversationId: number) => void,
  onDeepAnalysisStarted?: () => void,
): Promise<void> {
  const token = getToken();
  const res = await fetch(`${BASE}/api/coach/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (res.status === 401) {
    clearToken();
    window.location.assign("/login");
    return;
  }
  if (!res.ok || !res.body) {
    throw new Error(`Chat stream failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? ""; // last part may be incomplete, keep it for next read

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;

      let json: {
        content?: string;
        done?: boolean;
        showPosition?: ShowPositionEvent;
        conversationId?: number;
        deep?: boolean;
      };
      try {
        json = JSON.parse(line.slice("data:".length).trim());
      } catch {
        continue; // ignore malformed frames rather than crashing the stream
      }

      if (json.done) {
        onDone();
        return;
      }
      if (typeof json.content === "string") {
        onChunk(json.content);
      }
      if (json.showPosition && typeof json.showPosition.ply === "number") {
        onShowPosition?.(json.showPosition);
      }
      if (typeof json.conversationId === "number") {
        onConversationCreated?.(json.conversationId);
      }
      if (json.deep) {
        onDeepAnalysisStarted?.();
      }
    }
  }

  onDone(); // safety net if the stream closes without an explicit {"done": true}
}
