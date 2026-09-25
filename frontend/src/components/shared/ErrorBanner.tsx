import { AlertTriangle } from "lucide-react";

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-blunder/30 bg-blunder/10 px-4 py-3 text-sm text-ink">
      <div className="flex items-center gap-2">
        <AlertTriangle className="size-4 shrink-0 text-blunder" />
        <span>{message}</span>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-blunder underline-offset-2 hover:underline"
        >
          Retry
        </button>
      )}
    </div>
  );
}
