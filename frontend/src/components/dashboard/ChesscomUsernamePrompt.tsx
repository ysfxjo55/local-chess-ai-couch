import { useState, type FormEvent } from "react";
import { Puzzle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/**
 * Shown once, until the account has a Chess.com username on file. Sync used
 * to be hardcoded to one shared account for every app user — this is what
 * makes it per-user, and it's also the plain-language "just ask for the
 * username" onboarding step that was asked for.
 */
export function ChesscomUsernamePrompt() {
  const { refreshMe } = useAuth();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.setChesscomUsername({ chesscom_username: value.trim() });
      await refreshMe();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save that — try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-xl border border-amber/30 bg-amber/5 p-5">
      <div className="flex items-start gap-3">
        <Puzzle className="mt-0.5 size-5 shrink-0 text-amber" />
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold text-ink">Connect your Chess.com account</h2>
          <p className="mt-1 text-sm text-ink-muted">
            What's your Chess.com username? Once it's set, Sync will pull your
            own games and analysis — this only needs to be done once.
          </p>
          <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-2 sm:flex-row">
            <Input
              autoFocus
              placeholder="e.g. ysfxjo2"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              required
              minLength={3}
              className="sm:max-w-xs"
            />
            <Button type="submit" disabled={submitting || value.trim().length < 3}>
              {submitting ? "Saving…" : "Save"}
            </Button>
          </form>
          {error && <p className="mt-2 text-sm text-blunder">{error}</p>}
        </div>
      </div>
    </div>
  );
}
