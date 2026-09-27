import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FloatingPieces } from "@/components/shared/FloatingPieces";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";

type AccessMode = "sign-in" | "create" | "claim";

export default function Login() {
  const { login, register, claimLegacy, status } = useAuth();
  const [mode, setMode] = useState<AccessMode>("sign-in");
  const [username, setUsername] = useState("");
  const [chesscomUsername, setChesscomUsername] = useState("");
  const [password, setPassword] = useState("");
  const [registrationCode, setRegistrationCode] = useState("");
  const [claimCode, setClaimCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === "authed") return <Navigate to="/" replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "sign-in") await login(username, password);
      else if (mode === "create") await register(username, password, registrationCode);
      else await claimLegacy(chesscomUsername, password, claimCode);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not reach the server. Check the connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const creating = mode === "create";
  const claiming = mode === "claim";
  const identityReady = claiming ? chesscomUsername.trim().length >= 3 : username.trim().length >= 3;
  const passwordMinLength = creating ? 12 : 8;
  const passwordTooShort = password.length > 0 && password.length < passwordMinLength;
  const claimCodeTooShort = claimCode.length > 0 && claimCode.length < 8;
  const switchMode = (next: AccessMode) => {
    setMode(next);
    setError(null);
    setPassword("");
    setRegistrationCode("");
    setClaimCode("");
  };

  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-obsidian px-4">
      <FloatingPieces />
      <main className="relative z-10 w-full max-w-md" aria-labelledby="login-title">
        <div className="mb-10 text-center">
          <div className="mb-3 text-5xl" aria-hidden="true">♞</div>
          <h1 id="login-title" className="text-2xl font-semibold text-ink">Chess Coach</h1>
          <p className="mt-2 text-sm text-ink-muted">Your game history, practice record, and coaching plan stay tied to your account.</p>
        </div>

        <section className="rounded-xl border border-slate-border bg-slate-surface p-6 sm:p-8">
          <div className="mb-6 grid grid-cols-3 rounded-lg bg-slate-surface-raised p-1" role="tablist" aria-label="Account access">
            <button type="button" role="tab" aria-selected={mode === "sign-in"} onClick={() => switchMode("sign-in")} className={`rounded-md px-2 py-2 text-xs font-medium sm:text-sm ${mode === "sign-in" ? "bg-amber text-obsidian" : "text-ink-muted"}`}>Sign in</button>
            <button type="button" role="tab" aria-selected={creating} onClick={() => switchMode("create")} className={`rounded-md px-2 py-2 text-xs font-medium sm:text-sm ${creating ? "bg-amber text-obsidian" : "text-ink-muted"}`}>Create</button>
            <button type="button" role="tab" aria-selected={claiming} onClick={() => switchMode("claim")} className={`rounded-md px-2 py-2 text-xs font-medium sm:text-sm ${claiming ? "bg-amber text-obsidian" : "text-ink-muted"}`}>Claim old data</button>
          </div>

          {claiming && <p className="mb-5 rounded-lg border border-amber/25 bg-amber/5 px-3 py-2 text-sm text-ink-muted">Use this once after the upgrade to secure your existing Chess.com-linked game history with a new password.</p>}

          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {claiming ? (
              <div className="space-y-2">
                <Label htmlFor="chesscom-username">Existing Chess.com username</Label>
                <Input id="chesscom-username" autoComplete="username" autoFocus placeholder="Your Chess.com username" value={chesscomUsername} onChange={(event) => setChesscomUsername(event.target.value)} required minLength={3} maxLength={64} />
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="username">Account username</Label>
                <Input id="username" autoComplete="username" autoFocus placeholder="e.g. ysfxjo" value={username} onChange={(event) => setUsername(event.target.value)} aria-describedby="username-help" required minLength={3} maxLength={64} />
                <p id="username-help" className="text-xs text-ink-muted">Use 3–64 letters, numbers, dots, dashes, or underscores.</p>
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="password">{claiming ? "New password" : "Password"}</Label>
              <Input id="password" type="password" autoComplete={mode === "sign-in" ? "current-password" : "new-password"} placeholder={mode === "sign-in" ? "Your password" : `At least ${passwordMinLength} characters`} value={password} onChange={(event) => setPassword(event.target.value)} aria-invalid={passwordTooShort} aria-describedby="password-help" required minLength={passwordMinLength} maxLength={256} />
              {passwordTooShort ? (
                <p id="password-help" className="text-xs text-blunder">Need at least {passwordMinLength} characters ({password.length}/{passwordMinLength} so far).</p>
              ) : creating ? (
                <p id="password-help" className="text-xs text-ink-muted">Use at least 12 characters. Your Chess.com username is connected after sign-in.</p>
              ) : claiming ? (
                <p id="password-help" className="text-xs text-ink-muted">Use at least 8 characters for your new password.</p>
              ) : null}
            </div>
            {creating && (
              <div className="space-y-2">
                <Label htmlFor="registration-code">Registration code <span className="text-ink-muted">(if your deployment requires one)</span></Label>
                <Input id="registration-code" type="password" autoComplete="off" value={registrationCode} onChange={(event) => setRegistrationCode(event.target.value)} />
              </div>
            )}
            {claiming && (
              <div className="space-y-2">
                <Label htmlFor="claim-code">Legacy account claim code</Label>
                <Input id="claim-code" type="password" autoComplete="off" value={claimCode} onChange={(event) => setClaimCode(event.target.value)} aria-invalid={claimCodeTooShort} aria-describedby="claim-code-help" required minLength={8} maxLength={256} />
                <p id="claim-code-help" className={`text-xs ${claimCodeTooShort ? "text-blunder" : "text-ink-muted"}`}>
                  {claimCodeTooShort ? `Need at least 8 characters (${claimCode.length}/8 so far).` : "At least 8 characters."}
                </p>
              </div>
            )}
            {error && <p role="alert" className="rounded-md bg-blunder/10 px-3 py-2 text-sm text-blunder">{error}</p>}
            <Button type="submit" className="w-full" disabled={submitting || !identityReady || password.length < passwordMinLength || (claiming && claimCode.length < 8)}>
              {submitting ? <LoadingSpinner className="size-4" /> : creating ? "Create secure account" : claiming ? "Claim and secure my data" : "Sign in"}
            </Button>
          </form>
        </section>
      </main>
    </div>
  );
}
