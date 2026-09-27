import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { api, clearToken, getToken, setToken } from "./api";
import { queryClient } from "./queryClient";

interface AuthState {
  username: string | null;
  chesscomUsername: string | null;
  timezone: string | null;
  status: "loading" | "authed" | "anon";
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, registrationCode?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const anonymous: AuthState = { username: null, chesscomUsername: null, timezone: null, status: "anon" };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ ...anonymous, status: "loading" });

  function applyMe(me: Awaited<ReturnType<typeof api.me>>) {
    setState({ username: me.username, chesscomUsername: me.chesscom_username, timezone: me.timezone, status: "authed" });
  }

  function clearSession() {
    clearToken();
    queryClient.cancelQueries();
    queryClient.clear();
    setState(anonymous);
  }

  useEffect(() => {
    const controller = new AbortController();
    const token = getToken();
    if (!token) {
      setState(anonymous);
    } else {
      api.me(controller.signal).then(applyMe).catch((error) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) clearSession();
      });
    }
    const onUnauthenticated = () => clearSession();
    window.addEventListener("chess-coach:unauthenticated", onUnauthenticated);
    return () => {
      controller.abort();
      window.removeEventListener("chess-coach:unauthenticated", onUnauthenticated);
    };
  // `clearSession` only uses stable module helpers plus this component state setter.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function authenticate(tokenPromise: Promise<{ access_token: string }>) {
    const { access_token } = await tokenPromise;
    setToken(access_token);
    try {
      const me = await api.me();
      applyMe(me);
    } catch (error) {
      clearSession();
      throw error;
    }
  }

  async function login(username: string, password: string) {
    await authenticate(api.login({ username: username.trim(), password }));
  }

  async function register(username: string, password: string, registrationCode?: string) {
    await authenticate(api.register({ username: username.trim(), password, registration_code: registrationCode || undefined }));
  }

  async function logout() {
    try {
      if (getToken()) await api.logout();
    } catch {
      // Local logout must still complete if the server has already expired the token.
    } finally {
      clearSession();
    }
  }

  async function refreshMe() {
    const me = await api.me();
    applyMe(me);
  }

  return <AuthContext.Provider value={{ ...state, login, register, logout, refreshMe }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  if (status === "loading") {
    return <div className="flex h-dvh items-center justify-center bg-background"><div className="size-8 animate-spin rounded-full border-2 border-slate-border border-t-amber" /></div>;
  }
  if (status === "anon") return <Navigate to="/login" replace />;
  return <>{children}</>;
}
