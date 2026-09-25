import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { Navigate } from "react-router-dom";
import { api, clearToken, getToken, setToken } from "./api";

interface AuthState {
  username: string | null;
  chesscomUsername: string | null;
  status: "loading" | "authed" | "anon";
}

interface AuthContextValue extends AuthState {
  quickStart: (chesscomUsername: string) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    username: null,
    chesscomUsername: null,
    status: "loading",
  });

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setState({ username: null, chesscomUsername: null, status: "anon" });
      return;
    }
    api
      .me()
      .then((me) =>
        setState({ username: me.username, chesscomUsername: me.chesscom_username, status: "authed" }),
      )
      .catch(() => setState({ username: null, chesscomUsername: null, status: "anon" }));
  }, []);

  async function quickStart(chesscomUsername: string) {
    const { access_token } = await api.quickStart({ chesscom_username: chesscomUsername });
    setToken(access_token);
    const me = await api.me();
    setState({ username: me.username, chesscomUsername: me.chesscom_username, status: "authed" });
  }

  function logout() {
    clearToken();
    setState({ username: null, chesscomUsername: null, status: "anon" });
  }

  async function refreshMe() {
    const me = await api.me();
    setState((s) => ({ ...s, username: me.username, chesscomUsername: me.chesscom_username }));
  }

  return (
    <AuthContext.Provider value={{ ...state, quickStart, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <div className="flex h-dvh items-center justify-center bg-background">
        <div className="size-8 animate-spin rounded-full border-2 border-slate-border border-t-amber" />
      </div>
    );
  }
  if (status === "anon") {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
