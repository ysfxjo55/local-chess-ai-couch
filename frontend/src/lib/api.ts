import type {
  AnalysisResponse,
  ClaimAccountRequest,
  CoachHistoryResponse,
  CompletePlanItemResponse,
  ConversationListResponse,
  DailyPlanResponse,
  GameDetail,
  InsightsRuleListResponse,
  LoginRequest,
  MeResponse,
  PaginatedGamesResponse,
  PlayerProfileResponse,
  PuzzleAttemptRequest,
  PuzzleAttemptResponse,
  PuzzleExplanationResponse,
  PuzzleGameListResponse,
  PuzzleGuessRequest,
  PuzzleGuessResponse,
  PuzzleOut,
  PuzzleStatsResponse,
  RegisterRequest,
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
  TokenResponse,
  UpdateProfileRequest,
} from "./apiTypes";

const TOKEN_KEY = "cc_token";
const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const REQUEST_TIMEOUT_MS = 25_000;

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

function errorDetail(body: unknown, fallback: string): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => typeof item === "object" && item !== null && "msg" in item ? String(item.msg) : String(item)).join("; ");
  }
  return fallback;
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const signal = opts.signal ? AbortSignal.any([opts.signal, timeout]) : timeout;
  let response: Response;
  try {
    response = await fetch(`${BASE}/api${path}`, {
      ...opts,
      signal,
      headers: {
        ...(opts.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...opts.headers,
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError(408, "The request timed out. Check the connection and try again.");
    }
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "Could not reach the server. Check the connection and try again.");
  }

  if (response.status === 401) {
    clearToken();
    window.dispatchEvent(new Event("chess-coach:unauthenticated"));
    throw new ApiError(401, "Your session has ended. Please sign in again.");
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    throw new ApiError(response.status, errorDetail(body, response.statusText || "Request failed"));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  me: (signal?: AbortSignal) => request<MeResponse>("/auth/me", { signal }),
  login: (body: LoginRequest) => request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  register: (body: RegisterRequest) => request<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  claimLegacy: (body: ClaimAccountRequest) => request<TokenResponse>("/auth/claim", { method: "POST", body: JSON.stringify(body) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  updateProfile: (body: UpdateProfileRequest) => request<MeResponse>("/auth/profile", { method: "PUT", body: JSON.stringify(body) }),
  setChesscomUsername: (body: SetChesscomUsernameRequest) => request<MeResponse>("/auth/chesscom-username", { method: "PUT", body: JSON.stringify(body) }),

  syncGames: () => request<import("./apiTypes").SyncStatusResponse>("/games/sync", { method: "POST" }),
  syncStatus: (signal?: AbortSignal) => request<import("./apiTypes").SyncStatusResponse>("/games/sync/status", { signal }),
  listGames: (limit: number, offset: number, signal?: AbortSignal) => request<PaginatedGamesResponse>(`/games?limit=${limit}&offset=${offset}`, { signal }),
  getGame: (id: number, signal?: AbortSignal) => request<GameDetail>(`/games/${id}`, { signal }),
  triggerAnalysis: (id: number) => request<AnalysisResponse>(`/games/${id}/analysis`, { method: "POST" }),

  statsOverview: (range: StatsRange, signal?: AbortSignal) => request<StatsOverview>(`/stats/overview?range=${range}`, { signal }),
  repertoire: (range: StatsRange, minGames = 3, signal?: AbortSignal) => request<RepertoireResponse>(`/stats/repertoire?range=${range}&min_games=${minGames}`, { signal }),

  dailyPlan: (signal?: AbortSignal) => request<DailyPlanResponse>("/learning/daily-plan", { signal }),
  playerProfile: (signal?: AbortSignal) => request<PlayerProfileResponse>("/learning/profile", { signal }),
  completePlanItem: (id: number) => request<CompletePlanItemResponse>(`/learning/daily-plan/items/${id}/complete`, { method: "POST" }),

  clearGameChat: (gameId: number) => request<{ cleared: boolean }>(`/coach/games/${gameId}/history`, { method: "DELETE" }),
  listRules: () => request<InsightsRuleListResponse>("/coach/rules"),
  deleteRule: (id: number) => request<{ deleted: boolean }>(`/coach/rules/${id}`, { method: "DELETE" }),
  listConversations: () => request<ConversationListResponse>("/coach/conversations"),
  getConversationMessages: (id: number) => request<CoachHistoryResponse>(`/coach/conversations/${id}`),
  deleteConversation: (id: number) => request<{ deleted: boolean }>(`/coach/conversations/${id}`, { method: "DELETE" }),

  nextPuzzle: (gameId?: number, signal?: AbortSignal) => request<PuzzleOut | null>(`/puzzles/next${gameId != null ? `?game_id=${gameId}` : ""}`, { signal }),
  puzzleGames: (signal?: AbortSignal) => request<PuzzleGameListResponse>("/puzzles/games", { signal }),
  attemptPuzzle: (body: PuzzleAttemptRequest) => request<PuzzleAttemptResponse>("/puzzles/attempt", { method: "POST", body: JSON.stringify(body) }),
  puzzleStats: (signal?: AbortSignal) => request<PuzzleStatsResponse>("/puzzles/stats", { signal }),
  explainPuzzle: (gameId: number, ply: number, signal?: AbortSignal) => request<PuzzleExplanationResponse>(`/puzzles/${gameId}/${ply}/explain`, { signal }),
  guessPuzzle: (gameId: number, ply: number, body: PuzzleGuessRequest) => request<PuzzleGuessResponse>(`/puzzles/${gameId}/${ply}/guess`, { method: "POST", body: JSON.stringify(body) }),

  sparringLevels: () => request<SparringLevelsResponse>("/sparring/levels"),
  sparringTargetPreview: () => request<SparringTargetPreview | null>("/sparring/target-preview"),
  sparringStart: (body: SparringStartRequest) => request<SparringStartResponse>("/sparring/start", { method: "POST", body: JSON.stringify(body) }),
  sparringMove: (sessionId: string, body: SparringMoveRequest) => request<SparringMoveResponse>(`/sparring/${sessionId}/move`, { method: "POST", body: JSON.stringify(body) }),
  sparringTakeback: (sessionId: string) => request<SparringTakebackResponse>(`/sparring/${sessionId}/takeback`, { method: "POST" }),
  sparringAbandon: (sessionId: string) => request<{ abandoned: boolean }>(`/sparring/${sessionId}`, { method: "DELETE" }),
};
