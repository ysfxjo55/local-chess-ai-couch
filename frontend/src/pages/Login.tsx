import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FloatingPieces } from "@/components/shared/FloatingPieces";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";

export default function Login() {
  const { login, register, status } = useAuth();
  const [mode, setMode] = useState<"sign-in" | "create">("sign-in");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [registrationCode, setRegistrationCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === "authed") return <Navigate to="/" replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "sign-in") await login(username, password);
      else await register(username, password, registrationCode);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not reach the server. Check the connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const creating = mode === "create";
  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-obsidian px-4">
      <FloatingPieces />
      <main className="relative z-10 w-full max-w-md" aria-labelledby="login-title">
        <div className="mb-10 text-center">
          <div className="mb-3 text-5xl" aria-hidden="true">♞</div>
          <h1 id="login-title" className="text-2xl font-semibold text-ink">Chess Coach</h1>
          <p className="mt-2 text-sm text-ink-muted">Your game history, practice record, and coaching plan stay tied to your account.</p>
        </div>

        <section className="rounded-xl border border-slate-border bg-slate-surface p-8">
          <div className="mb-6 grid grid-cols-2 rounded-lg bg-slate-surface-raised p-1" role="tablist" aria-label="Account access">
            <button type="button" role="tab" aria-selected={!creating} onClick={() => { setMode("sign-in"); setError(null); }} className={`rounded-md px-3 py-2 text-sm font-medium ${!creating ? "bg-amber text-obsidian" : "text-ink-muted"}`}>Sign in</button>
            <button type="button" role="tab" aria-selected={creating} onClick={() => { setMode("create"); setError(null); }} className={`rounded-md px-3 py-2 text-sm font-medium ${creating ? "bg-amber text-obsidian" : "text-ink-muted"}`}>Create account</button>
          </div>
          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            <div className="space-y-2">
              <Label htmlFor="username">Account username</Label>
              <Input id="username" autoComplete="username" autoFocus placeholder="e.g. ysfxjo" value={username} onChange={(event) => setUsername(event.target.value)} aria-describedby="username-help" required minLength={3} maxLength={64} />
              <p id="username-help" className="text-xs text-ink-muted">Use 3–64 letters, numbers, dots, dashes, or underscores.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete={creating ? "new-password" : "current-password"} placeholder="At least 12 characters" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={12} maxLength={256} />
              {creating && <p className="text-xs text-ink-muted">Use at least 12 characters. Your Chess.com username is connected after sign-in.</p>}
            </div>
            {creating && (
              <div className="space-y-2">
                <Label htmlFor="registration-code">Registration code <span className="text-ink-muted">(if your deployment requires one)</span></Label>
                <Input id="registration-code" type="password" autoComplete="off" value={registrationCode} onChange={(event) => setRegistrationCode(event.target.value)} />
              </div>
            )}
            {error && <p role="alert" className="rounded-md bg-blunder/10 px-3 py-2 text-sm text-blunder">{error}</p>}
            <Button type="submit" className="w-full" disabled={submitting || username.trim().length < 3 || password.length < 12}>
              {submitting ? <LoadingSpinner className="size-4" /> : creating ? "Create secure account" : "Sign in"}
            </Button>
          </form>
        </section>
      </main>
    </div>
  );
}
