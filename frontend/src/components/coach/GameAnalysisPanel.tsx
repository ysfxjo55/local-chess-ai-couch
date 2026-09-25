import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { markdownComponents } from "./markdownComponents";
import { useTriggerAnalysis } from "@/hooks/useGameAnalysis";
import { ApiError } from "@/lib/api";

/**
 * Surfaces coach_analysis — the AI's plain-English "here's what went wrong
 * and why" writeup. This data has existed on the backend all along
 * (auto-generated for losses at sync time, or available on demand via
 * useTriggerAnalysis), but nothing in the UI ever actually rendered it —
 * this is the fix for that gap. Used on both GameDetail and the Puzzles
 * reveal, so "why was this a blunder" has one real answer wherever you ask.
 */
export function GameAnalysisPanel({
  gameId,
  analysis,
}: {
  gameId: number;
  analysis: string | null;
}) {
  const trigger = useTriggerAnalysis(gameId);
  const resolvedAnalysis = trigger.data?.coach_analysis ?? analysis;

  if (resolvedAnalysis) {
    return (
      <div className="rounded-lg border border-slate-border bg-slate-surface p-4">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
          {resolvedAnalysis}
        </ReactMarkdown>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-border bg-slate-surface p-4 text-sm">
      <p className="mb-3 text-ink-muted">No AI analysis yet for this game.</p>
      <Button
        size="sm"
        onClick={() => trigger.mutate()}
        disabled={trigger.isPending}
        className="gap-1.5"
      >
        {trigger.isPending ? <LoadingSpinner className="size-3.5" /> : <Sparkles className="size-3.5" />}
        {trigger.isPending ? "Analyzing…" : "Explain what went wrong"}
      </Button>
      {trigger.isError && (
        <p className="mt-2 text-xs text-blunder">
          {trigger.error instanceof ApiError ? trigger.error.message : "Could not generate analysis."}
        </p>
      )}
    </div>
  );
}
