import { cn } from "@/lib/utils";

export function LoadingSpinner({ className }: { className?: string }) {
  return (
    <div
      role="status"
      aria-label="Loading"
      className={cn(
        "size-5 animate-spin rounded-full border-2 border-slate-border border-t-amber",
        className,
      )}
    />
  );
}
