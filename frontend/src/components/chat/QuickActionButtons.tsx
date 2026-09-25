import type { MoveOut } from "@/lib/apiTypes";

interface QuickActionButtonsProps {
  currentMove: MoveOut | undefined;
  onSend: (message: string) => void;
  disabled?: boolean;
}

/**
 * Context-aware preset prompts for the game-scoped chat. Each one becomes
 * the literal message sent — visible in the chat exactly as-is, no hidden
 * context needed beyond what's already in the text, since the backend's
 * own system prompt already has the full per-game move analysis.
 */
export function QuickActionButtons({
  currentMove,
  onSend,
  disabled,
}: QuickActionButtonsProps) {
  if (!currentMove) return null;

  const prompts: string[] = [];
  if (currentMove.classification && currentMove.is_player_move) {
    prompts.push(
      `Why is ${currentMove.label} (${currentMove.san}) classified as ${currentMove.classification}?`,
    );
  }
  if (currentMove.best_move && currentMove.best_move !== currentMove.san) {
    prompts.push(`Show me the idea behind ${currentMove.best_move} instead.`);
  }
  prompts.push(`What plan should I be forming around ${currentMove.label}?`);

  return (
    <div className="flex flex-wrap gap-1.5">
      {prompts.map((prompt) => (
        <button
          key={prompt}
          disabled={disabled}
          onClick={() => onSend(prompt)}
          className="rounded-full border border-slate-border px-2.5 py-1 text-xs text-ink-muted transition-colors hover:border-amber/40 hover:text-amber disabled:pointer-events-none disabled:opacity-50"
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}
