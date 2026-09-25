import type {
  AnalysisResponse,
  CoachHistoryResponse,
  ConversationListResponse,
  GameDetail,
  InsightsRuleListResponse,
  MeResponse,
  PaginatedGamesResponse,
  PuzzleAttemptRequest,
  PuzzleAttemptResponse,
  PuzzleExplanationResponse,
  PuzzleGameListResponse,
  PuzzleGuessRequest,
  PuzzleGuessResponse,
  PuzzleOut,
  PuzzleStatsResponse,
  RepertoireResponse,
  SetChesscomUsernameRequest,
  SparringLevelsResponse,
  SparringMoveRequest,
  SparringMoveResponse,
  SparringStartRequest,
  SparringStartResponse,
  SparringTakebackResponse,
  SparringTargetPreview,
  StatsOverview,
  StatsRange,
  SyncStatusResponse,
  TokenResponse,
} from "./apiTypes";

const TOKEN_KEY = "cc_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * In development, requests go through the Vite dev-server proxy (see
 * vite.config.ts, `/api` -> http://localhost:8000), so a relative path is
 * enough — VITE_API_BASE_URL is unset and BASE is "". In production, the
 * frontend (Cloudflare Pages) and backend (your Mac, via Cloudflare Tunnel)
 * are two different origins, so the built app needs an absolute URL —
 * VITE_API_BASE_URL is baked in at build time from .env.production.
 */
const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE}/api${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...opts.headers,
    },
  });

  if (res.status === 401) {
    clearToken();
    if (window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
    throw new ApiError(401, "Not authenticated");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? "Request failed");
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  me: () => request<MeResponse>("/auth/me"),
  quickStart: (body: SetChesscomUsernameRequest) =>
    request<TokenResponse>("/auth/quick-start", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  setChesscomUsername: (body: SetChesscomUsernameRequest) =>
    request<MeResponse>("/auth/chesscom-username", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  syncGames: () => request<SyncStatusResponse>("/games/sync", { method: "POST" }),
  syncStatus: () => request<SyncStatusResponse>("/games/sync/status"),
  listGames: (limit: number, offset: number) =>
    request<PaginatedGamesResponse>(`/games?limit=${limit}&offset=${offset}`),
  getGame: (id: number) => request<GameDetail>(`/games/${id}`),
  triggerAnalysis: (id: number) =>
    request<AnalysisResponse>(`/games/${id}/analysis`, { method: "POST" }),

  statsOverview: (range: StatsRange) =>
    request<StatsOverview>(`/stats/overview?range=${range}`),

  repertoire: (range: StatsRange, minGames = 3) =>
    request<RepertoireResponse>(`/stats/repertoire?range=${range}&min_games=${minGames}`),

  clearGameChat: (gameId: number) =>
    request<{ cleared: boolean }>(`/coach/games/${gameId}/history`, { method: "DELETE" }),

  listRules: () => request<InsightsRuleListResponse>("/coach/rules"),
  deleteRule: (id: number) =>
    request<{ deleted: boolean }>(`/coach/rules/${id}`, { method: "DELETE" }),

  listConversations: () => request<ConversationListResponse>("/coach/conversations"),
  getConversationMessages: (id: number) =>
    request<CoachHistoryResponse>(`/coach/conversations/${id}`),
  deleteConversation: (id: number) =>
    request<{ deleted: boolean }>(`/coach/conversations/${id}`, { method: "DELETE" }),

  nextPuzzle: (gameId?: number) =>
    request<PuzzleOut | null>(`/puzzles/next${gameId != null ? `?game_id=${gameId}` : ""}`),
  puzzleGames: () => request<PuzzleGameListResponse>("/puzzles/games"),
  attemptPuzzle: (body: PuzzleAttemptRequest) =>
    request<PuzzleAttemptResponse>("/puzzles/attempt", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  puzzleStats: () => request<PuzzleStatsResponse>("/puzzles/stats"),
  explainPuzzle: (gameId: number, ply: number) =>
    request<PuzzleExplanationResponse>(`/puzzles/${gameId}/${ply}/explain`),
  guessPuzzle: (gameId: number, ply: number, body: PuzzleGuessRequest) =>
    request<PuzzleGuessResponse>(`/puzzles/${gameId}/${ply}/guess`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  sparringLevels: () => request<SparringLevelsResponse>("/sparring/levels"),
  sparringTargetPreview: () => request<SparringTargetPreview | null>("/sparring/target-preview"),
  sparringStart: (body: SparringStartRequest) =>
    request<SparringStartResponse>("/sparring/start", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  sparringMove: (sessionId: string, body: SparringMoveRequest) =>
    request<SparringMoveResponse>(`/sparring/${sessionId}/move`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  sparringTakeback: (sessionId: string) =>
    request<SparringTakebackResponse>(`/sparring/${sessionId}/takeback`, { method: "POST" }),
  sparringAbandon: (sessionId: string) =>
    request<{ abandoned: boolean }>(`/sparring/${sessionId}`, { method: "DELETE" }),
};
