from pydantic import BaseModel, ConfigDict
from datetime import datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class MeResponse(BaseModel):
    username: str
    chesscom_username: str | None = None

class SetChesscomUsernameRequest(BaseModel):
    chesscom_username: str

class QuickStartRequest(BaseModel):
    chesscom_username: str

class MoveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    san: str
    side: str
    is_player_move: bool
    eval_before: int
    eval_after: int
    cp_loss: int | None
    classification: str | None
    best_move: str | None
    puzzle_correct: bool | None = None


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str


class GameDetail(BaseModel):
    id: int
    event: str
    date: str
    white: str
    black: str
    result: str
    player: str
    player_color: str
    opponent: str
    player_outcome: str
    time_class: str | None = None
    moves: list[MoveOut]
    coach_analysis: str | None
    chat_history: list[ChatMessageOut]

class GameSyncItem(BaseModel):
    id: int
    opponent: str
    result: str
    player_color: str
    played_at: datetime
    time_class: str | None = None


class SyncResponse(BaseModel):
    new_games: int
    games: list[GameSyncItem]

class SyncBlunderHighlight(BaseModel):
    game_id: int
    opponent: str
    label: str
    san: str
    cp_loss: int


class SyncStatusResponse(BaseModel):
    # "idle": never synced (or nothing since server restart) · "running":
    # in progress · "done": finished · "error": failed, see `error`.
    status: str
    processed: int = 0
    total: int = 0
    new_games: int = 0
    games: list[GameSyncItem] = []
    error: str | None = None
    # Cheap, deterministic (no LLM) summary of the newly-synced games' own
    # flagged moves — shown as an immediate post-sync signal, distinct from
    # the slower per-game AI writeup.
    blunders_found: int = 0
    worst_blunder: SyncBlunderHighlight | None = None

class GameListItem(GameSyncItem):
    blunders: int
    mistakes: int
    inaccuracies: int
    player_outcome: str

class PaginatedGamesResponse(BaseModel):
    total: int
    games: list[GameListItem]

class AnalysisResponse(BaseModel):
    coach_analysis: str


class AccuracyTrend(BaseModel):
    date: str
    avg_cp_loss: float
    games: int

class WinByColor(BaseModel):
    White: float
    Black: float


class OpeningStat(BaseModel):
    opening: str
    games: int
    win_rate: float

class Blunders(BaseModel):
    opening: float
    middlegame: float
    endgame: float


class StatsOverview(BaseModel):
    accuracy_trend: list[AccuracyTrend]
    win_rate_by_color: WinByColor
    win_rate_by_opening: list[OpeningStat]
    blunder_rate_by_phase: Blunders


class CoachChatRequest(BaseModel):
    game_id: int | None
    message: str
    # Per-game chat only — which ply (0-indexed, matching MoveRecord.ply /
    # the moves[] array order) the player currently has selected in the
    # board/move-list UI. Without this the coach only ever sees a handful
    # of flagged moves, not the actual position being discussed.
    current_ply: int | None = None
    # Only meaningful when game_id is None (the global chat). None means
    # "start a new conversation" — the backend creates one on the first
    # message and reports its id back via the SSE stream.
    conversation_id: int | None = None
    # Explicit "Deep analysis" toggle (global chat only) — runs a real
    # per-move aggregation over the player's recent games instead of just
    # the always-on summary stats every message already gets.
    deep: bool = False

class CoachHistoryResponse(BaseModel):
    history: list[ChatMessageOut]

class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    created_at: datetime
    updated_at: datetime

class ConversationListResponse(BaseModel):
    conversations: list[ConversationOut]


class PuzzleOut(BaseModel):
    game_id: int
    ply: int
    label: str
    classification: str
    cp_loss: int | None
    opponent: str
    player_color: str
    time_class: str | None = None
    remaining: int
    total: int


class PuzzleAttemptRequest(BaseModel):
    game_id: int
    ply: int
    correct: bool


class PuzzleAttemptResponse(BaseModel):
    recorded: bool
    remaining: int


class PuzzleStatsResponse(BaseModel):
    total: int
    solved: int
    correct: int


class PuzzleExplanationResponse(BaseModel):
    explanation: str


class PuzzleGuessRequest(BaseModel):
    from_square: str
    to_square: str
    promotion: str | None = None


class PuzzleGameOption(BaseModel):
    game_id: int
    opponent: str
    count: int
    time_class: str | None = None
    played_at: datetime | None = None


class PuzzleGameListResponse(BaseModel):
    games: list[PuzzleGameOption]


class PuzzleGuessResponse(BaseModel):
    san: str
    classification: str
    cp_loss: int
    is_best: bool
    solved: bool


class RepertoireStat(BaseModel):
    opening: str
    player_color: str
    games: int
    win_rate: float
    draw_rate: float
    # Average centipawn loss on the player's own moves within the opening
    # phase (ply <= 20, same threshold as blunder_rate_by_phase) for this
    # specific opening+color — null if none of those moves have an eval yet.
    avg_cp_loss_opening: float | None


class RepertoireResponse(BaseModel):
    entries: list[RepertoireStat]


class InsightsRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    game_id: int | None
    content: str
    created_at: datetime


class InsightsRuleListResponse(BaseModel):
    rules: list[InsightsRuleOut]


class SparringLevelsResponse(BaseModel):
    levels: list[int]


class SparringTargetPreview(BaseModel):
    opening: str
    player_color: str
    win_rate: float
    games: int
    seed_moves: list[str] = []


class SparringStartRequest(BaseModel):
    maia_level: int = 1500
    target_weak_opening: bool = True


class SparringStartResponse(BaseModel):
    session_id: str
    fen: str
    player_color: str
    maia_level: int
    target: SparringTargetPreview | None
    seed_moves: list[str]
    moves: list[str]
    done: bool


class SparringMoveRequest(BaseModel):
    from_square: str
    to_square: str
    promotion: str | None = None


class SparringWarning(BaseModel):
    classification: str
    cp_loss: int
    matched_rule: str | None


class SparringMoveResponse(BaseModel):
    session_id: str
    fen: str
    player_san: str
    maia_san: str | None
    warning: SparringWarning | None
    done: bool
    result: str | None
    game_id: int | None


class SparringTakebackResponse(BaseModel):
    session_id: str
    fen: str
    moves: list[str]
