from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{3,64}$"
CHESSCOM_USERNAME_PATTERN = r"^[A-Za-z0-9_-]{3,64}$"


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=256)


class RegisterRequest(LoginRequest):
    password: str = Field(min_length=12, max_length=256)
    registration_code: str | None = Field(default=None, max_length=256)


class ClaimAccountRequest(BaseModel):
    chesscom_username: str = Field(min_length=3, max_length=64, pattern=CHESSCOM_USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=256)
    claim_code: str = Field(min_length=8, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class MeResponse(BaseModel):
    username: str
    chesscom_username: str | None = None
    timezone: str = "UTC"


class SetChesscomUsernameRequest(BaseModel):
    chesscom_username: str = Field(min_length=3, max_length=64, pattern=CHESSCOM_USERNAME_PATTERN)


class UpdateProfileRequest(BaseModel):
    chesscom_username: str | None = Field(default=None, min_length=3, max_length=64, pattern=CHESSCOM_USERNAME_PATTERN)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def clean_timezone(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class MoveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    san: str
    side: str
    is_player_move: bool
    eval_before: int | None
    eval_after: int | None
    cp_loss: int | None
    classification: str | None
    best_move: str | None
    puzzle_correct: bool | None = None


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: Literal["user", "assistant"]
    content: str


class GameDetail(BaseModel):
    id: int
    event: str | None
    date: str | None
    white: str | None
    black: str | None
    result: str | None
    player: str
    player_color: str | None
    opponent: str | None
    player_outcome: str | None
    opening: str | None = None
    time_class: str | None = None
    moves: list[MoveOut]
    coach_analysis: str | None
    chat_history: list[ChatMessageOut]


class GameSyncItem(BaseModel):
    id: int
    opponent: str | None
    result: str | None
    player_color: str | None
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
    job_id: str | None = None
    status: Literal["idle", "queued", "running", "done", "error"]
    processed: int = 0
    total: int = 0
    new_games: int = 0
    games: list[GameSyncItem] = Field(default_factory=list)
    error: str | None = None
    blunders_found: int = 0
    worst_blunder: SyncBlunderHighlight | None = None


class GameListItem(GameSyncItem):
    blunders: int
    mistakes: int
    inaccuracies: int
    player_outcome: str | None
    opening: str | None = None


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
    game_id: int | None = None
    message: str = Field(min_length=1, max_length=4000)
    current_ply: int | None = Field(default=None, ge=0, le=1000)
    conversation_id: int | None = Field(default=None, ge=1)
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
    opponent: str | None
    player_color: str | None
    time_class: str | None = None
    remaining: int
    total: int
    due_at: datetime | None = None
    interval_days: int = 0


class PuzzleAttemptRequest(BaseModel):
    game_id: int = Field(ge=1)
    ply: int = Field(ge=0)
    outcome: Literal["gave_up"]
    attempts_before_result: int = Field(default=0, ge=0, le=99)
    response_seconds: int | None = Field(default=None, ge=0, le=86400)
    idempotency_key: str = Field(min_length=8, max_length=96)


class PuzzleAttemptResponse(BaseModel):
    recorded: bool
    remaining: int
    due_at: datetime
    interval_days: int


class PuzzleStatsResponse(BaseModel):
    total: int
    due: int
    solved: int
    correct: int


class PuzzleExplanationResponse(BaseModel):
    explanation: str


class PuzzleGuessRequest(BaseModel):
    from_square: str = Field(pattern=r"^[a-h][1-8]$")
    to_square: str = Field(pattern=r"^[a-h][1-8]$")
    promotion: Literal["q", "r", "b", "n"] | None = None
    attempts_before_result: int = Field(default=0, ge=0, le=99)
    response_seconds: int | None = Field(default=None, ge=0, le=86400)
    idempotency_key: str = Field(min_length=8, max_length=96)


class PuzzleGameOption(BaseModel):
    game_id: int
    opponent: str | None
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
    recorded: bool = False
    remaining: int | None = None
    due_at: datetime | None = None


class RepertoireStat(BaseModel):
    opening: str
    player_color: str
    games: int
    win_rate: float
    draw_rate: float
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
    seed_moves: list[str] = Field(default_factory=list)


class SparringStartRequest(BaseModel):
    maia_level: int = Field(default=1500, ge=1100, le=2200)
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
    from_square: str = Field(pattern=r"^[a-h][1-8]$")
    to_square: str = Field(pattern=r"^[a-h][1-8]$")
    promotion: Literal["q", "r", "b", "n"] | None = None


class SparringWarning(BaseModel):
    classification: Literal["Blunder", "Mistake"]
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


class SkillStateOut(BaseModel):
    skill_key: str
    mastery: float
    confidence: float
    evidence_count: int
    priority: float
    last_evidence_at: datetime | None


class PlayerProfileResponse(BaseModel):
    generated_at: datetime
    games_analyzed: int
    strengths: list[SkillStateOut]
    focus_areas: list[SkillStateOut]
    methodology: str


class DailyPlanItemOut(BaseModel):
    id: int
    ordinal: int
    kind: Literal["review", "new_puzzle", "focus", "sparring"]
    reference_id: str | None
    title: str
    rationale: str
    target_minutes: int
    completed_at: datetime | None


class DailyPlanResponse(BaseModel):
    id: int
    plan_date: str
    timezone: str
    generated_at: datetime
    items: list[DailyPlanItemOut]


class CompletePlanItemResponse(BaseModel):
    completed: bool
    completed_at: datetime | None
