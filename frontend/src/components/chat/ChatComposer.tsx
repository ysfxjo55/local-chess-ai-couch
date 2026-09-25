import { useState, type KeyboardEvent } from "react";
import { Send, Microscope } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function ChatComposer({
  onSend,
  disabled,
  showDeepToggle,
}: {
  onSend: (message: string, deep?: boolean) => void;
  disabled?: boolean;
  /** Global chat only — deep analysis spans many games, which a single
   * game's chat is already scoped away from. */
  showDeepToggle?: boolean;
}) {
  const [value, setValue] = useState("");
  const [deep, setDeep] = useState(false);

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, deep);
    setValue("");
    setDeep(false); // armed per-message, like the tone switcher is per-session but this isn't
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="space-y-1.5">
      {showDeepToggle && (
        <button
          type="button"
          onClick={() => setDeep((d) => !d)}
          className={cn(
            "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
            deep
              ? "border-amber/50 bg-amber/10 text-amber"
              : "border-slate-border text-ink-muted hover:text-ink",
          )}
          aria-pressed={deep}
        >
          <Microscope className="size-3.5" />
          Deep analysis
          {deep && (
            <span className="text-ink-muted">
              — mention how many games (e.g. "last 60"), or it'll use 30
            </span>
          )}
        </button>
      )}
      <div className="flex items-end gap-2">
        <Textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask the coach anything…"
          rows={1}
          className="max-h-32 min-h-11 flex-1 resize-none py-2.5"
        />
        <Button
          size="icon"
          className="size-11 shrink-0"
          disabled={disabled || !value.trim()}
          onClick={submit}
          aria-label="Send message"
        >
          <Send className="size-4" />
        </Button>
      </div>
    </div>
  );
}
