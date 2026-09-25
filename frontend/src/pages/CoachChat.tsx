import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { useConversationMessages } from "@/hooks/useConversations";
import { useMediaQuery } from "@/hooks/useMediaQuery";

export default function CoachChat() {
  const isDesktop = useMediaQuery("(min-width: 768px)");
  // `selection` drives which ChatPanel instance is mounted (its `key`) and
  // which conversation's history to fetch — it only ever changes from an
  // explicit user action (sidebar click / "New chat").
  const [selection, setSelection] = useState<{ mountKey: string; id: number | null }>({
    mountKey: "new-0",
    id: null,
  });
  // `highlightId` is just which sidebar row looks active. It's allowed to
  // change mid-stream (when a brand-new conversation gets its id back)
  // WITHOUT touching `selection` — updating `selection.mountKey` there
  // would remount ChatPanel and abort the reply that's still streaming in.
  const [highlightId, setHighlightId] = useState<number | null>(null);
  // Desktop: sidebar is a persistent column, open by default. Mobile: it
  // would squeeze the chat into a sliver, so it starts closed and opens as
  // a full overlay instead (see `overlay` prop below).
  const [sidebarOpen, setSidebarOpen] = useState(isDesktop);
  const queryClient = useQueryClient();

  const messages = useConversationMessages(selection.id);
  const isSwitchingConversation = selection.id !== null && messages.isLoading;

  function handleSelect(id: number | null) {
    setSelection({ mountKey: id === null ? `new-${Date.now()}` : `conv-${id}`, id });
    setHighlightId(id);
  }

  return (
    <div className="flex h-[calc(100dvh-140px)] min-h-[420px] flex-col gap-3 md:h-[calc(100dvh-100px)]">
      <div>
        <h1 className="text-lg font-semibold text-ink">Coach</h1>
        <p className="text-sm text-ink-muted">
          Ask about your recent play across all your games — pick up an old
          conversation from the sidebar, or start a new one.
        </p>
      </div>
      <div className="relative flex min-h-0 flex-1 overflow-hidden rounded-xl border border-slate-border">
        <ConversationSidebar
          activeConversationId={highlightId}
          onSelect={handleSelect}
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen((o) => !o)}
          overlay={!isDesktop}
        />
        <div className="min-w-0 flex-1">
          {isSwitchingConversation ? (
            <div className="flex h-full items-center justify-center">
              <LoadingSpinner className="size-6" />
            </div>
          ) : (
            <ChatPanel
              key={selection.mountKey}
              gameId={null}
              conversationId={selection.id}
              initialHistory={messages.data?.history ?? []}
              onConversationCreated={(id) => {
                setHighlightId(id);
                queryClient.invalidateQueries({ queryKey: ["conversations"] });
              }}
              emptyHint="Ask things like “what should I focus on improving?” or “what's my biggest weakness lately?”"
            />
          )}
        </div>
      </div>
    </div>
  );
}
