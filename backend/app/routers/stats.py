from backend.app.db import get_db
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..auth import get_current_user
from typing import Literal
from ..schemas import (
    StatsOverview,
    AccuracyTrend,
    WinByColor,
    OpeningStat,
    Blunders,
    RepertoireStat,
    RepertoireResponse,
)
from datetime import datetime, timedelta
from ..models import Game, MoveRecord, User
from sqlalchemy import func, case

router = APIRouter(prefix="/api/stats", tags=["stats"])


def range_to_cutoff(range: Literal["7d", "30d", "90d", "all"]) -> datetime | None:
    if range == "7d":
        return datetime.utcnow() - timedelta(days=7)
    if range == "30d":
        return datetime.utcnow() - timedelta(days=30)
    if range == "90d":
        return datetime.utcnow() - timedelta(days=90)
    return None


def compute_stats_overview(db: Session, user_id: int, cutoff_date: datetime | None) -> StatsOverview:
    """Shared by GET /api/stats/overview and the coach chat's context —
    one place computing "how has this player actually been doing," so the
    coach references the same numbers the Insights page shows."""
    user_filter = Game.user_id == user_id

    rows = (
        db.query(
            func.date(Game.played_at).label("day"),
            func.avg(MoveRecord.cp_loss).label("avg_loss"),
            func.count(func.distinct(MoveRecord.game_id)).label("game_count"),
        )
        .join(Game, MoveRecord.game_id == Game.id)
        .filter(MoveRecord.is_player_move == True, MoveRecord.cp_loss.isnot(None))
        .filter(user_filter)
        .filter(Game.played_at >= cutoff_date if cutoff_date else True)
        .group_by(func.date(Game.played_at))
        .order_by(func.date(Game.played_at))
        .all()
    )
    accuracy_trend = [
        AccuracyTrend(date=row.day, avg_cp_loss=row.avg_loss, games=row.game_count)
        for row in rows
    ]

    color_rows = (
        db.query(
            Game.player_color,
            func.count(Game.id).label("total_games"),
            func.count(case((Game.player_outcome == "Win", Game.id))).label("wins"),
        )
        .filter(user_filter)
        .filter(Game.played_at >= cutoff_date if cutoff_date else True)
        .group_by(Game.player_color)
        .all()
    )
    win_rates = {"White": 0.0, "Black": 0.0}

    for i in color_rows:
        if i.total_games > 0:
            win_rates[i.player_color] = i.wins / i.total_games
    win_rate_by_color = WinByColor(**win_rates)

    opening_rows = (
        db.query(
            Game.opening,
            func.count(Game.id).label("total_games"),
            func.count(case((Game.player_outcome == "Win", Game.id))).label("wins"),
        )
        .filter(user_filter)
        .filter(Game.played_at >= cutoff_date if cutoff_date else True)
        .group_by(Game.opening)
        .order_by(func.count(Game.id).desc())
        .limit(10)
        .all()
    )
    win_rate_by_opening = [
        OpeningStat(
            opening=row.opening,
            games=row.total_games,
            win_rate=round(row.wins / row.total_games, 2) if row.total_games > 0 else 0.0,
        )
        for row in opening_rows
    ]

    phase_expr = case(
        (MoveRecord.ply <= 20, "opening"),
        (MoveRecord.ply <= 60, "middlegame"),
        else_="endgame",
    ).label("phase")

    phase_rows = (
        db.query(
            phase_expr,
            func.count(MoveRecord.id).label("total_moves"),
            func.count(case((MoveRecord.classification == "Blunder", MoveRecord.id))).label("blunders"),
        )
        .join(Game, MoveRecord.game_id == Game.id)
        .filter(
            MoveRecord.is_player_move == True,
            user_filter,
            Game.played_at >= cutoff_date if cutoff_date else True,
        )
        .group_by(phase_expr)
        .all()
    )

    phase_blunder_rates = {"opening": 0.0, "middlegame": 0.0, "endgame": 0.0}

    for row in phase_rows:
        if row.total_moves > 0:
            phase_blunder_rates[row.phase] = round(row.blunders / row.total_moves, 4)

    blunder_rate_by_phase = Blunders(**phase_blunder_rates)

    return StatsOverview(
        accuracy_trend=accuracy_trend,
        win_rate_by_color=win_rate_by_color,
        win_rate_by_opening=win_rate_by_opening,
        blunder_rate_by_phase=blunder_rate_by_phase,
    )


@router.get("/overview", response_model=StatsOverview)
def stats_record(db: Session = Depends(get_db), current_user: User = Depends(get_current_user), range: Literal["7d", "30d", "90d", "all"] = Query(default="30d")):
    cutoff_date = range_to_cutoff(range)
    return compute_stats_overview(db, current_user.id, cutoff_date)


@router.get("/repertoire", response_model=RepertoireResponse)
def repertoire_diagnostic(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    range: Literal["7d", "30d", "90d", "all"] = Query(default="all"),
    min_games: int = Query(default=3, ge=1, le=50),
):
    """Per (opening, color) breakdown — not just how often you reach an
    opening, but where specifically it's losing you games, split by color
    since the same opening name means a different repertoire branch
    depending which side you're on. Sorted worst win rate first: the whole
    point is telling you exactly which branch to go review, not just which
    one you play most."""
    cutoff_date = range_to_cutoff(range)
    user_filter = Game.user_id == current_user.id
    date_filter = Game.played_at >= cutoff_date if cutoff_date else True

    game_rows = (
        db.query(
            Game.opening,
            Game.player_color,
            func.count(Game.id).label("total_games"),
            func.count(case((Game.player_outcome == "Win", Game.id))).label("wins"),
            func.count(case((Game.player_outcome == "Draw", Game.id))).label("draws"),
        )
        .filter(user_filter, date_filter, Game.opening != "Unknown Opening")
        .group_by(Game.opening, Game.player_color)
        .having(func.count(Game.id) >= min_games)
        .all()
    )

    cp_rows = (
        db.query(
            Game.opening,
            Game.player_color,
            func.avg(MoveRecord.cp_loss).label("avg_loss"),
        )
        .join(Game, MoveRecord.game_id == Game.id)
        .filter(
            user_filter,
            date_filter,
            MoveRecord.is_player_move == True,  # noqa: E712
            MoveRecord.cp_loss.isnot(None),
            MoveRecord.ply <= 20,
        )
        .group_by(Game.opening, Game.player_color)
        .all()
    )
    cp_lookup = {(row.opening, row.player_color): row.avg_loss for row in cp_rows}

    entries = [
        RepertoireStat(
            opening=row.opening,
            player_color=row.player_color,
            games=row.total_games,
            win_rate=round(row.wins / row.total_games, 2),
            draw_rate=round(row.draws / row.total_games, 2),
            avg_cp_loss_opening=(
                round(cp_lookup[(row.opening, row.player_color)], 1)
                if cp_lookup.get((row.opening, row.player_color)) is not None
                else None
            ),
        )
        for row in game_rows
    ]
    entries.sort(key=lambda e: e.win_rate)

    return RepertoireResponse(entries=entries)
