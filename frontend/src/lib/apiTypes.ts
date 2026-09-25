// Mirrors backend/app/schemas.py field-for-field. Do not rename fields here
// without updating API_CONTRACT.md first — see CLAUDE.md's role split.

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}

export interface MeResponse {
  username: string;
  chesscom_username: string | null;
}

export interface SetChesscomUsernameRequest {
  chesscom_username: string;
}

export type QuickStartRequest = SetChesscomUsernameRequest;

export type PlayerColor = "White" | "Black";
export type PlayerOutcome = "Win" | "Loss" | "Draw" | "Unknown";
export type TimeClass = "bullet" | "blitz" | "rapid" | "daily" | null;
export type Classification =
  | "Blunder"
  | "Mistake"
  | "Inaccuracy"
  | "Good"
  | "Excellent"
  | null;

export interface GameSyncItem {
  id: number;
  opponent: string;
  result: string;
  player_color: PlayerColor;
  played_at: string;
  time_class: TimeClass;
}

export interface SyncResponse {
  new_games: number;
  games: GameSyncItem[];
}

export interface SyncBlunderHighlight {
  game_id: number;
  opponent: string;
  label: string;
  san: string;
  cp_loss: number;
}

export interface SyncStatusResponse {
  status: "idle" | "running" | "done" | "error";
  processed: number;
  total: number;
  new_games: number;
  games: GameSyncItem[];
  error: string | null;
  blunders_found: number;
  worst_blunder: SyncBlunderHighlight | null;
}

export interface GameListItem extends GameSyncItem {
  blunders: number;
  mistakes: number;
  inaccuracies: number;
  player_outcome: PlayerOutcome;
  /** Proposed API_CONTRACT.md addition — not shipped by the backend yet. */
  opening?: string;
}

export interface PaginatedGamesResponse {
  total: number;
  games: GameListItem[];
}

export interface MoveOut {
  label: string;
  san: string;
  side: "White" | "Black";
  is_player_move: boolean;
  eval_before: number;
  eval_after: number;
  cp_loss: number | null;
  classification: Classification;
  best_move: string | null;
  puzzle_correct: boolean | null;
}

export interface ChatMessageOut {
  role: "user" | "assistant";
  content: string;
}

export interface GameDetail {
  id: number;
  event: string;
  date: string;
  white: string;
  black: string;
  result: string;
  player: string;
  player_color: PlayerColor;
  opponent: string;
  player_outcome: PlayerOutcome;
  time_class: TimeClass;
  moves: MoveOut[];
  coach_analysis: string | null;
  chat_history: ChatMessageOut[];
  /** Proposed API_CONTRACT.md addition — not shipped by the backend yet. */
  opening?: string;
}

export interface AnalysisResponse {
  coach_analysis: string;
}

export interface AccuracyTrendPoint {
  date: string;
  avg_cp_loss: number;
  games: number;
}

export interface WinRateByColor {
  White: number;
  Black: number;
}

export interface OpeningStat {
  opening: string;
  games: number;
  win_rate: number;
}

export interface BlunderRateByPhase {
  opening: number;
  middlegame: number;
  endgame: number;
}

export interface StatsOverview {
  accuracy_trend: AccuracyTrendPoint[];
  win_rate_by_color: WinRateByColor;
  win_rate_by_opening: OpeningStat[];
  blunder_rate_by_phase: BlunderRateByPhase;
}

export interface RepertoireStat {
  opening: string;
  player_color: PlayerColor;
  games: number;
  win_rate: number;
  draw_rate: number;
  avg_cp_loss_opening: number | null;
}

export interface RepertoireResponse {
  entries: RepertoireStat[];
}

export type StatsRange = "7d" | "30d" | "90d" | "all";

export interface CoachChatRequest {
  game_id: number | null;
  message: string;
  /** Only meaningful when game_id is null. null = start a new conversation. */
  conversation_id?: number | null;
  /** Global chat only — the "Deep analysis" toggle. Runs a real per-move
   * aggregation over recent games instead of the always-on summary stats. */
  deep?: boolean;
  /** Per-game chat only — the ply (0-indexed, matches moves[] order) the
   * board/move-list UI currently has selected, so the coach is grounded in
   * the real position instead of guessing it from memory. */
  current_ply?: number | null;
}

export interface CoachHistoryResponse {
  history: ChatMessageOut[];
}

export interface ConversationOut {
  id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  conversations: ConversationOut[];
}

export interface InsightsRuleOut {
  id: number;
  game_id: number | null;
  content: string;
  created_at: string;
}

export interface InsightsRuleListResponse {
  rules: InsightsRuleOut[];
}

export interface SparringLevelsResponse {
  levels: number[];
}

export interface SparringTargetPreview {
  opening: string;
  player_color: PlayerColor;
  win_rate: number;
  games: number;
  seed_moves: string[];
}

export interface SparringStartRequest {
  maia_level: number;
  target_weak_opening: boolean;
}

export interface SparringStartResponse {
  session_id: string;
  fen: string;
  player_color: PlayerColor;
  maia_level: number;
  target: SparringTargetPreview | null;
  seed_moves: string[];
  moves: string[];
  done: boolean;
}

export interface SparringMoveRequest {
  from_square: string;
  to_square: string;
  promotion?: string | null;
}

export interface SparringWarning {
  classification: "Blunder" | "Mistake";
  cp_loss: number;
  matched_rule: string | null;
}

export interface SparringMoveResponse {
  session_id: string;
  fen: string;
  player_san: string;
  maia_san: string | null;
  warning: SparringWarning | null;
  done: boolean;
  result: string | null;
  game_id: number | null;
}

export interface SparringTakebackResponse {
  session_id: string;
  fen: string;
  moves: string[];
}

export interface PuzzleOut {
  game_id: number;
  ply: number;
  label: string;
  classification: Classification;
  cp_loss: number | null;
  opponent: string;
  player_color: PlayerColor;
  time_class: TimeClass;
  remaining: number;
  total: number;
}

export interface PuzzleAttemptRequest {
  game_id: number;
  ply: number;
  correct: boolean;
}

export interface PuzzleAttemptResponse {
  recorded: boolean;
  remaining: number;
}

export interface PuzzleStatsResponse {
  total: number;
  solved: number;
  correct: number;
}

export interface PuzzleExplanationResponse {
  explanation: string;
}

export interface PuzzleGameOption {
  game_id: number;
  opponent: string;
  count: number;
  time_class: TimeClass;
  played_at: string | null;
}

export interface PuzzleGameListResponse {
  games: PuzzleGameOption[];
}

export interface PuzzleGuessRequest {
  from_square: string;
  to_square: string;
  promotion?: string | null;
}

export interface PuzzleGuessResponse {
  san: string;
  classification: Classification;
  cp_loss: number;
  is_best: boolean;
  solved: boolean;
}
