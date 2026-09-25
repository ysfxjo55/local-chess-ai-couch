import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { FloatingPieces } from "@/components/shared/FloatingPieces";

export default function Login() {
  const { quickStart, status } = useAuth();
  const [chesscomUsername, setChesscomUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === "authed") return <Navigate to="/" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await quickStart(chesscomUsername.trim());
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not reach the server. Is the backend running?",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-obsidian px-4">
      <FloatingPieces />

      <div className="relative z-10 w-full max-w-md">
        <div className="mb-10 text-center">
          <div className="mb-3 text-5xl">♞</div>
          <h1 className="text-2xl font-semibold text-ink">Chess Coach</h1>
          <p className="mt-2 text-sm text-ink-muted">
            Enter your Chess.com username to get started
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-5 rounded-xl border border-slate-border bg-slate-surface p-8"
        >
          <div className="space-y-2">
            <Label htmlFor="chesscomUsername">Chess.com Username</Label>
            <Input
              id="chesscomUsername"
              autoComplete="username"
              autoFocus
              placeholder="e.g. magnuscarlsen"
              value={chesscomUsername}
              onChange={(e) => setChesscomUsername(e.target.value)}
              required
            />
            <p className="text-xs text-ink-muted">
              We'll pull all your games and analyze them with Stockfish
            </p>
          </div>

          {error && (
            <p className="rounded-md bg-blunder/10 px-3 py-2 text-sm text-blunder">
              {error}
            </p>
          )}

          <Button
            type="submit"
            className="w-full"
            disabled={submitting || !chesscomUsername.trim()}
          >
            {submitting ? <LoadingSpinner className="size-4" /> : "Continue"}
          </Button>
        </form>
      </div>
    </div>
  );
}
