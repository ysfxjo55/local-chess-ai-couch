import { Plus, Trash2, PanelLeftClose, PanelLeftOpen, MessageCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useConversationsList, useDeleteConversation } from "@/hooks/useConversations";
import { Skeleton } from "@/components/ui/skeleton";

function relativeDate(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

interface ConversationSidebarProps {
  activeConversationId: number | null;
  onSelect: (id: number | null) => void;
  isOpen: boolean;
  onToggle: () => void;
  /** On phones the sidebar overlays the chat instead of squeezing it into a
   * sliver — it needs the full list width to be usable, and there isn't
   * room to show both side by side. */
  overlay?: boolean;
}

/** ChatGPT-style collapsible list of past global-chat conversations. */
export function ConversationSidebar({
  activeConversationId,
  onSelect,
  isOpen,
  onToggle,
  overlay = false,
}: ConversationSidebarProps) {
  const { data, isLoading } = useConversationsList();
  const deleteConversation = useDeleteConversation();

  function handleDelete(e: React.MouseEvent, id: number) {
    e.stopPropagation();
    if (!window.confirm("Delete this conversation? This can't be undone.")) return;
    deleteConversation.mutate(id);
    if (id === activeConversationId) onSelect(null);
  }

  function handleSelect(id: number | null) {
    onSelect(id);
    if (overlay) onToggle(); // picking a chat (or "New chat") closes the overlay on mobile
  }

  if (!isOpen) {
    if (overlay) {
      // Collapsed + overlay (mobile): just a small opener, no reserved column.
      return (
        <button
          onClick={onToggle}
          title="Open conversation list"
          aria-label="Open conversation list"
          className="absolute left-2 top-2 z-20 flex size-8 items-center justify-center rounded-md border border-slate-border bg-slate-surface/90 text-ink-muted backdrop-blur hover:text-ink"
        >
          <PanelLeftOpen className="size-4" />
        </button>
      );
    }
    return (
      <div className="flex w-11 shrink-0 flex-col items-center gap-2 border-r border-slate-border pt-1">
        <button
          onClick={onToggle}
          title="Open conversation list"
          className="flex size-8 items-center justify-center rounded-md text-ink-muted hover:bg-slate-surface hover:text-ink"
        >
          <PanelLeftOpen className="size-4" />
        </button>
        <button
          onClick={() => onSelect(null)}
          title="New chat"
          className="flex size-8 items-center justify-center rounded-md text-amber hover:bg-slate-surface"
        >
          <Plus className="size-4" />
        </button>
      </div>
    );
  }

  const list = (
    <div
      className={cn(
        "flex w-64 shrink-0 flex-col border-r border-slate-border",
        overlay && "h-full w-72 max-w-[80vw] border-r-0",
      )}
    >
      <div className="flex items-center justify-between p-2">
        <button
          onClick={() => handleSelect(null)}
          className="flex flex-1 items-center gap-2 rounded-md border border-slate-border px-2.5 py-1.5 text-sm text-ink transition-colors hover:bg-slate-surface"
        >
          <Plus className="size-4 text-amber" />
          New chat
        </button>
        <button
          onClick={onToggle}
          title="Close conversation list"
          className="ml-1 flex size-8 shrink-0 items-center justify-center rounded-md text-ink-muted hover:bg-slate-surface hover:text-ink"
        >
          <PanelLeftClose className="size-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {isLoading ? (
          <div className="space-y-1.5">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-11 rounded-md" />
            ))}
          </div>
        ) : !data?.conversations.length ? (
          <p className="px-2 py-3 text-xs text-ink-muted">No conversations yet.</p>
        ) : (
          <div className="space-y-0.5">
            {data.conversations.map((c) => (
              <button
                key={c.id}
                onClick={() => handleSelect(c.id)}
                className={cn(
                  "group flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors",
                  c.id === activeConversationId
                    ? "bg-slate-surface-raised text-ink"
                    : "text-ink-muted hover:bg-slate-surface hover:text-ink",
                )}
              >
                <MessageCircle className="size-3.5 shrink-0" />
                <span className="min-w-0 flex-1 truncate">{c.title || "New chat"}</span>
                <span className="shrink-0 text-[11px] text-ink-muted group-hover:hidden">
                  {relativeDate(c.updated_at)}
                </span>
                <span
                  role="button"
                  onClick={(e) => handleDelete(e, c.id)}
                  className="hidden shrink-0 rounded p-0.5 text-ink-muted hover:text-blunder group-hover:block"
                >
                  <Trash2 className="size-3.5" />
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  if (!overlay) return list;

  return (
    <div className="absolute inset-0 z-20 flex">
      <div className="bg-obsidian shadow-xl">{list}</div>
      <button
        aria-label="Close conversation list"
        onClick={onToggle}
        className="flex-1 bg-obsidian/60 backdrop-blur-sm"
      />
    </div>
  );
}
