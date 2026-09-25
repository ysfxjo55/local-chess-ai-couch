import re
import chess
from ..schemas import (
    CoachChatRequest,
    ChatMessageOut,
    CoachHistoryResponse,
    ConversationOut,
    ConversationListResponse,
    InsightsRuleOut,
    InsightsRuleListResponse,
)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from ..db import get_db
from ..auth import get_current_user
from ..models import Game, MoveRecord, ChatMessage, Conversation, InsightsRule, User
from ..schemas import MoveOut
from ..services.stockfish_analysis import build_analysis_summary, format_game_context
from ..services.coach_llm import (
    SYSTEM_PROMPT,
    SHOW_POSITION_TOOL,
    GET_GAME_DETAIL_TOOL,
    stream_coach_response_with_tools,
)
from .stats import compute_stats_overview
from fastapi.responses import StreamingResponse
import json

router = APIRouter(prefix="/api/coach", tags=["coach"])

TONE_PREFIX_RE = re.compile(r"^\[Respond in an? [^\]]*\]\n\n")

DEEP_ANALYSIS_DEFAULT_LIMIT = 30
DEEP_ANALYSIS_MAX_LIMIT = 300
GAME_COUNT_RE = re.compile(r"(\d{1,4})\s*games?\b", re.IGNORECASE)


def parse_requested_game_count(message: str) -> int:
    """Reads a number straight out of what the player actually typed —
    "last 60 games", "past 90 games", "100 games" all match. Falls back to
    the default when nothing's specified, so "deep analysis" with no number
    still works exactly as before."""
    match = GAME_COUNT_RE.search(message)
    if not match:
        return DEEP_ANALYSIS_DEFAULT_LIMIT
    return max(1, min(int(match.group(1)), DEEP_ANALYSIS_MAX_LIMIT))


def _piece_of(san: str) -> str:
    if san.startswith("O-O"):
        return "castling"
    return {"N": "knight", "B": "bishop", "R": "rook", "Q": "queen", "K": "king"}.get(
        san[0] if san else "", "pawn"
    )


def _phase_of(ply: int) -> str:
    if ply <= 20:
        return "opening"
    if ply <= 60:
        return "middlegame"
    return "endgame"


def build_full_game_detail_text(db: Session, game: Game, current_username: str) -> str:
    """Full move list + mistake analysis for ONE game — the same shape the
    per-game chat gets, built on demand for the global chat's
    `get_game_detail` tool so it can actually answer "what was my first
    move against X" instead of asking the player to paste a PGN."""
    g_moves = (
        db.query(MoveRecord).filter(MoveRecord.game_id == game.id).order_by(MoveRecord.ply).all()
    )
    movetext_parts = [
        f"{i // 2 + 1}. {m.san}" if i % 2 == 0 else m.san for i, m in enumerate(g_moves)
    ]
    move_dicts = [MoveOut.model_validate(m).model_dump() for m in g_moves]
    ctx = {
        "event": game.event,
        "date": game.date,
        "white": game.white,
        "black": game.black,
        "result": game.result,
        "player": current_username,
        "player_color": game.player_color,
        "opponent": game.opponent,
        "player_outcome": game.player_outcome,
    }
    return (
        f"{format_game_context(ctx)}\n"
        f"Full Move List (standard notation): {' '.join(movetext_parts)}\n\n"
        f"{build_analysis_summary(ctx, move_dicts)}"
    )


def build_pattern_summary(overview) -> str:
    """All-time playing-pattern lines shared by the global chat and (now)
    the per-game chat — this is the "knows me across every game" context,
    not just whatever's true of the one game currently being discussed."""
    pattern_lines = [
        f"- Win rate as White: {round(overview.win_rate_by_color.White * 100)}%, "
        f"as Black: {round(overview.win_rate_by_color.Black * 100)}%",
        f"- Blunder rate by game phase: Opening {round(overview.blunder_rate_by_phase.opening * 100)}%, "
        f"Middlegame {round(overview.blunder_rate_by_phase.middlegame * 100)}%, "
        f"Endgame {round(overview.blunder_rate_by_phase.endgame * 100)}%",
    ]
    if overview.win_rate_by_opening:
        top_openings = ", ".join(
            f"{o.opening} ({round(o.win_rate * 100)}% over {o.games} games)"
            for o in overview.win_rate_by_opening[:5]
        )
        pattern_lines.append(f"- Most-played openings: {top_openings}")
    if len(overview.accuracy_trend) >= 2:
        first, last = overview.accuracy_trend[0], overview.accuracy_trend[-1]
        trend = "improving" if last.avg_cp_loss < first.avg_cp_loss else "getting worse"
        pattern_lines.append(
            f"- Accuracy trend: avg centipawn loss went from {round(first.avg_cp_loss)} "
            f"({first.date}) to {round(last.avg_cp_loss)} ({last.date}) — {trend} over that span"
        )
    return "\n".join(pattern_lines)


RULES_INJECTED_LIMIT = 20


def build_learned_rules_section(db: Session, user_id: int) -> str:
    """Accumulated takeaways from past lost games — the "learns you over
    time" piece. Injected into every coach chat, per-game and global alike,
    so a mistake tonight that matches a rule from three weeks ago actually
    gets flagged instead of treated as new. Capped and newest-first so the
    prompt doesn't grow unbounded as the list accumulates over months."""
    rules = (
        db.query(InsightsRule)
        .filter(InsightsRule.user_id == user_id)
        .order_by(InsightsRule.created_at.desc())
        .limit(RULES_INJECTED_LIMIT)
        .all()
    )
    if not rules:
        return ""
    lines = "\n".join(f"- {r.content}" for r in rules)
    return (
        f"\n\n### Rules Learned From This Player's Past Losses (apply these "
        f"proactively — if something happening now matches one, say so "
        f"explicitly rather than treating it as a fresh observation)\n{lines}"
    )


def compute_deep_analysis(db: Session, user_id: int, limit: int = DEEP_ANALYSIS_DEFAULT_LIMIT) -> str:
    """On-demand, heavier aggregation over the player's most recent games —
    real per-move querying (piece involved, phase, per-opening blunder
    correlation, per-game breakdown), not the same always-on summary every
    other message already gets. Only runs when explicitly requested (the
    global chat's "Deep analysis" toggle), since it's real extra querying
    over potentially thousands of move rows.
    """
    games = (
        db.query(Game)
        .filter(Game.user_id == user_id)
        .order_by(Game.played_at.desc())
        .limit(limit)
        .all()
    )
    if not games:
        return "No games synced yet — nothing to analyze."

    games_by_id = {g.id: g for g in games}
    moves = (
        db.query(MoveRecord)
        .filter(MoveRecord.game_id.in_(games_by_id.keys()), MoveRecord.is_player_move == True)
        .all()
    )

    wins = sum(1 for g in games if g.player_outcome == "Win")
    losses = sum(1 for g in games if g.player_outcome == "Loss")
    draws = sum(1 for g in games if g.player_outcome == "Draw")
    white_games = [g for g in games if g.player_color == "White"]
    black_games = [g for g in games if g.player_color == "Black"]
    white_wins = sum(1 for g in white_games if g.player_outcome == "Win")
    black_wins = sum(1 for g in black_games if g.player_outcome == "Win")

    blunders = [m for m in moves if m.classification == "Blunder"]
    mistakes = [m for m in moves if m.classification == "Mistake"]
    inaccuracies = [m for m in moves if m.classification == "Inaccuracy"]
    total_moves = len(moves)

    phase_blunder_counts = {"opening": 0, "middlegame": 0, "endgame": 0}
    for m in blunders:
        phase_blunder_counts[_phase_of(m.ply)] += 1

    piece_counts: dict[str, int] = {}
    for m in blunders + mistakes:
        piece_counts[_piece_of(m.san)] = piece_counts.get(_piece_of(m.san), 0) + 1
    top_pieces = sorted(piece_counts.items(), key=lambda kv: -kv[1])[:3]

    opening_blunder_counts: dict[str, int] = {}
    for m in blunders:
        opening = games_by_id[m.game_id].opening or "Unknown Opening"
        opening_blunder_counts[opening] = opening_blunder_counts.get(opening, 0) + 1
    top_blunder_openings = sorted(opening_blunder_counts.items(), key=lambda kv: -kv[1])[:5]

    moves_by_game: dict[int, list] = {}
    for m in moves:
        moves_by_game.setdefault(m.game_id, []).append(m)

    per_game_lines = []
    for g in games:
        game_moves = moves_by_game.get(g.id, [])
        # Every game gets at least one concrete, citable moment — not just
        # the ones that happened to contain a blunder. A clean win with no
        # mistakes used to produce nothing here at all, which is exactly
        # why the model had nothing specific to say about it and fell back
        # to generic praise ("good tactical awareness").
        worst = max(
            (m for m in game_moves if m.classification in ("Blunder", "Mistake")),
            key=lambda m: m.cp_loss or 0,
            default=None,
        )
        best = min(
            (m for m in game_moves if m.classification in ("Excellent", "Good") and m.cp_loss is not None),
            key=lambda m: m.cp_loss,
            default=None,
        )
        line = (
            f"{g.played_at.strftime('%Y-%m-%d')} {g.player_color} vs {g.opponent} "
            f"({g.player_outcome}, {g.result}), opening: {g.opening or 'Unknown'}"
        )
        moments = []
        if best:
            moments.append(f"strong moment: {best.san} (~move {best.ply // 2 + 1}, {best.classification})")
        if worst:
            moments.append(
                f"worst moment: {worst.san} (~move {worst.ply // 2 + 1}, {worst.classification}, "
                f"lost {worst.cp_loss}cp)"
            )
        if moments:
            line += " — " + "; ".join(moments)
        per_game_lines.append(line)

    lines = [
        f"Analyzed your last {len(games)} games "
        f"({games[-1].played_at.strftime('%Y-%m-%d')} to {games[0].played_at.strftime('%Y-%m-%d')}).",
        f"Record: {wins}W-{losses}L-{draws}D. "
        f"As White: {white_wins}/{len(white_games)} wins. As Black: {black_wins}/{len(black_games)} wins.",
        f"Across {total_moves} of your own moves: {len(blunders)} blunders, {len(mistakes)} mistakes, "
        f"{len(inaccuracies)} inaccuracies"
        + (f" ({round(100 * len(blunders) / total_moves)}% blunder rate)." if total_moves else "."),
        f"Blunders by phase: opening {phase_blunder_counts['opening']}, "
        f"middlegame {phase_blunder_counts['middlegame']}, endgame {phase_blunder_counts['endgame']}.",
    ]
    if top_pieces:
        lines.append(
            "Pieces most involved in blunders/mistakes: "
            + ", ".join(f"{p} ({c})" for p, c in top_pieces)
        )
    if top_blunder_openings:
        lines.append(
            "Openings with the most blunders: "
            + ", ".join(f"{o} ({c})" for o, c in top_blunder_openings)
        )
    lines.append("Per-game breakdown (newest first):\n" + "\n".join(per_game_lines))

    return "\n".join(lines)


def make_title(message: str) -> str:
    """Short conversation title derived from its first message — strips the
    frontend's tone-instruction prefix first, same pattern the client uses
    to display it, so titles never show that bracketed text either."""
    clean = TONE_PREFIX_RE.sub("", message).strip()
    return (clean[:50] + "…") if len(clean) > 50 else clean


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return ConversationListResponse(
        conversations=[ConversationOut.model_validate(c) for c in conversations]
    )


@router.get("/conversations/{conversation_id}", response_model=CoachHistoryResponse)
def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id, Conversation.user_id == current_user.id
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    return CoachHistoryResponse(history=[ChatMessageOut.model_validate(m) for m in messages])


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id, Conversation.user_id == current_user.id
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conversation)  # cascades to its messages
    db.commit()
    return {"deleted": True}


@router.delete("/games/{game_id}/history")
def clear_game_chat(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-game chat has no separate conversation entity — it's one thread
    per game, so 'start over' just means wiping that game's messages."""
    game = db.query(Game).filter(Game.id == game_id, Game.user_id == current_user.id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    db.query(ChatMessage).filter(
        ChatMessage.game_id == game_id, ChatMessage.user_id == current_user.id
    ).delete(synchronize_session=False)
    db.commit()
    return {"cleared": True}


@router.get("/rules", response_model=InsightsRuleListResponse)
def list_rules(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rules = (
        db.query(InsightsRule)
        .filter(InsightsRule.user_id == current_user.id)
        .order_by(InsightsRule.created_at.desc())
        .all()
    )
    return InsightsRuleListResponse(rules=[InsightsRuleOut.model_validate(r) for r in rules])


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rule = db.query(InsightsRule).filter(
        InsightsRule.id == rule_id, InsightsRule.user_id == current_user.id
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"deleted": True}


@router.post("/chat")
def coach_chat(payload: CoachChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    if payload.game_id is not None:
        chat = ChatMessage(
            user_id=current_user.id,
            game_id=payload.game_id,
            content=payload.message,
            role="user",
        )
        db.add(chat)
        db.commit()

        game = db.query(Game).filter(Game.id == payload.game_id, Game.user_id == current_user.id).first()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        ctx = {
            "event": game.event,
            "date": game.date,
            "white": game.white,
            "black": game.black,
            "result": game.result,
            "player": current_user.username,
            "player_color": game.player_color,
            "opponent": game.opponent,
            "player_outcome": game.player_outcome,
        }
        moves = db.query(MoveRecord).filter(MoveRecord.game_id == game.id).order_by(MoveRecord.ply).all()
        move_dicts = [MoveOut.model_validate(m).model_dump() for m in moves]
        game_format = format_game_context(ctx)
        analysis_summary = build_analysis_summary(ctx, move_dicts)

        # Full SAN move list, standard PGN movetext ("1. e4 e5 2. Nf3 ...").
        # Without this the coach only ever saw the flagged turning-point/
        # mistake moves above — never the actual game — so it had no real
        # way to know what's on the board when asked about a specific
        # position, and would guess/hallucinate piece placement.
        movetext_parts = []
        for i, m in enumerate(moves):
            movetext_parts.append(f"{i // 2 + 1}. {m.san}" if i % 2 == 0 else m.san)
        movetext = " ".join(movetext_parts)

        # Ground the exact position currently shown in the board/move-list
        # UI, if the client told us which ply that is — replaying the real
        # SAN sequence server-side into a real FEN, never trusting the model
        # to track the board itself.
        current_position_section = ""
        if payload.current_ply is not None and 0 <= payload.current_ply < len(moves):
            board = chess.Board()
            try:
                for m in moves[: payload.current_ply + 1]:
                    board.push_san(m.san)
                at_move = moves[payload.current_ply]
                current_position_section = (
                    f"\n\n### Position The Player Is Currently Looking At\n"
                    f"The board/move-list UI is currently showing the position right after "
                    f"{at_move.label} {at_move.san}. FEN: {board.fen()}\n"
                    f"Whenever the player says things like 'now', 'here', 'this position', "
                    f"'my move' without naming one, or asks what's possible 'right now', they "
                    f"mean THIS exact position — use the FEN above as ground truth for what's "
                    f"actually on which squares, don't infer it from memory of the move list."
                )
            except ValueError:
                pass  # a stored SAN failed to replay — skip rather than send a broken FEN

        # All-time patterns across every synced game — this is what makes
        # the per-game coach an actual personal assistant instead of a
        # one-off analyzer: it can connect what happened in THIS game to
        # the player's broader tendencies (e.g. "this is the same kind of
        # blunder you make in the endgame across your recent games").
        overview = compute_stats_overview(db, current_user.id, cutoff_date=None)
        pattern_summary = build_pattern_summary(overview)
        learned_rules_section = build_learned_rules_section(db, current_user.id)

        chat_history = db.query(ChatMessage).filter(
            ChatMessage.game_id == payload.game_id,
            ChatMessage.user_id == current_user.id,
        ).order_by(ChatMessage.created_at).all()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",
                "content": (
                    f"### Game Details\n{game_format}\n\n"
                    f"### Full Move List (standard notation)\n{movetext}\n\n"
                    f"### Move Analysis Summary\n{analysis_summary}"
                    f"{current_position_section}\n\n"
                    f"### This Player's All-Time Patterns (across every synced game, not just "
                    f"this one — use this to connect what happens in this game to their broader "
                    f"tendencies when it's genuinely relevant)\n{pattern_summary}"
                    f"{learned_rules_section}"
                )
            }
        ]
        messages_per_row = [
            {"role": msg.role, "content": msg.content} for msg in chat_history
        ]
        final_messages = messages + messages_per_row

        max_ply = len(moves) - 1

        def handle_game_tool_call(name: str, args: dict):
            if name == "show_position":
                return "Shown to the user.", args
            return "Unknown tool.", None

        def event_stream():
            content = ""
            for event in stream_coach_response_with_tools(
                final_messages, tools=[SHOW_POSITION_TOOL], tool_handler=handle_game_tool_call
            ):
                if event["type"] == "text":
                    content += event["content"]
                    yield f"data: {json.dumps({'content': event['content']})}\n\n"
                elif event["type"] == "tool" and event["name"] == "show_position":
                    args = event["event"]
                    # Compute the exact ply from (move_number, side) in code —
                    # never trust the model's own arithmetic for this.
                    move_number = args.get("move_number")
                    side = args.get("side")
                    if not isinstance(move_number, int) or side not in ("White", "Black"):
                        continue
                    ply = (move_number - 1) * 2 + (0 if side == "White" else 1)
                    if not (0 <= ply <= max_ply):
                        continue  # model referenced a move outside this game — skip silently
                    yield f"data: {json.dumps({'showPosition': {'ply': ply, 'caption': args.get('caption')}})}\n\n"

            chat_message = ChatMessage(
                user_id=current_user.id,
                game_id=payload.game_id,
                role="assistant",
                content=content,
            )
            db.add(chat_message)
            db.commit()

            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    else:
        # Global chat — ChatGPT-style multi-conversation. conversation_id is
        # None means "start a new one"; the new id is reported back to the
        # client via an SSE frame as soon as it's known.
        is_new_conversation = payload.conversation_id is None

        if is_new_conversation:
            conversation = Conversation(user_id=current_user.id, title=make_title(payload.message))
            db.add(conversation)
            db.flush()  # assigns conversation.id
        else:
            conversation = db.query(Conversation).filter(
                Conversation.id == payload.conversation_id,
                Conversation.user_id == current_user.id,
            ).first()
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")

        chat = ChatMessage(
            user_id=current_user.id,
            conversation_id=conversation.id,
            content=payload.message,
            role="user",
        )
        db.add(chat)
        conversation.updated_at = datetime.now()
        db.commit()

        chat_history = db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation.id,
        ).order_by(ChatMessage.created_at).all()

        all_games = db.query(Game).filter(Game.user_id == current_user.id).all()
        wins = 0
        losses = 0
        draws = 0

        for game in all_games:
            if game.player_outcome == "Win":
                wins += 1
            elif game.player_outcome == "Loss":
                losses += 1
            elif game.player_outcome == "Draw":
                draws += 1
        stats_summary = f"You've played {len(all_games)} games total: {wins} wins, {losses} losses, {draws} draws."

        # Explicit, date-ordered "what did I just play" grounding — without
        # this, the model has nothing telling it which game is actually
        # most recent (the "worst moves" list below is sorted by cp_loss,
        # not date, so it isn't a reliable stand-in for "my last game").
        recent_games = (
            db.query(Game)
            .filter(Game.user_id == current_user.id)
            .order_by(Game.played_at.desc())
            .limit(5)
            .all()
        )
        recent_games_summary = "\n".join(
            f"{g.played_at.strftime('%Y-%m-%d')}: {g.player_color} vs {g.opponent} — {g.player_outcome} ({g.result})"
            for g in recent_games
        ) or "No games synced yet."

        worst_moves = (
            db.query(MoveRecord, Game)
            .join(Game, MoveRecord.game_id == Game.id)
            .filter(
                Game.user_id == current_user.id,
                MoveRecord.is_player_move == True,
                MoveRecord.classification.in_(["Blunder", "Mistake"]),
            )
            .order_by(MoveRecord.cp_loss.desc())
            .limit(5)
            .all()
        )

        worst_moves_lines = [
            f"vs {game.opponent} on {game.date}: {move.san} was a {move.classification} (lost {move.cp_loss} cp)"
            for move, game in worst_moves
        ]
        worst_moves_summary = "\n".join(worst_moves_lines)

        overview = compute_stats_overview(db, current_user.id, cutoff_date=None)
        pattern_summary = build_pattern_summary(overview)
        learned_rules_section = build_learned_rules_section(db, current_user.id)

        context_sections = (
            f"### Overall Stats\n{stats_summary}\n\n"
            f"### Most Recent Games (newest first — use this, not the section below, "
            f"to answer questions about the player's last/latest game)\n{recent_games_summary}\n\n"
            f"### Playing Patterns (all-time)\n{pattern_summary}\n\n"
            f"### Worst Recent Moves (sorted by size of the mistake, NOT by date)\n{worst_moves_summary}"
            f"{learned_rules_section}"
        )
        messages_per_row = [
            {"role": msg.role, "content": msg.content} for msg in chat_history
        ]
        conversation_id = conversation.id

        def event_stream():
            if is_new_conversation:
                yield f"data: {json.dumps({'conversationId': conversation_id})}\n\n"

            sections = context_sections
            if payload.deep:
                # Emitted before the (blocking, real per-move query) deep
                # analysis runs, not after — so the frontend's "analyzing"
                # state actually covers the wait, instead of flashing right
                # before the reply starts.
                yield f"data: {json.dumps({'deep': True})}\n\n"
                # Honors a number the player actually typed ("last 60
                # games") — falls back to the default only when they didn't
                # ask for a specific window.
                game_limit = parse_requested_game_count(payload.message)
                sections += (
                    f"\n\n### Deep Analysis (last {game_limit} games, computed on request — "
                    f"this is real per-move data, prefer it over the sections above when they conflict. "
                    f"Write like a coach who actually watched these games, not a stats summary: cite "
                    f"specific moves by name and move number from the per-game breakdown below — e.g. "
                    f'"in your game against X, {{move}} on move {{n}} did this, which shows..." — for '
                    f"multiple different games, not just one example repeated. Never describe a game "
                    f"only in generic terms ('good tactical awareness', 'solid opening') without naming "
                    f"an actual move from it.)\n"
                    f"{compute_deep_analysis(db, current_user.id, limit=game_limit)}"
                )

            final_messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": sections},
            ] + messages_per_row

            def handle_global_tool_call(name: str, args: dict):
                if name != "get_game_detail":
                    return "Unknown tool.", None
                opponent = (args.get("opponent") or "").strip()
                query = db.query(Game).filter(Game.user_id == current_user.id)
                if opponent:
                    query = query.filter(Game.opponent.ilike(f"%{opponent}%"))
                game = query.order_by(Game.played_at.desc()).first()
                if not game:
                    return (
                        f"No game found matching opponent '{opponent}'." if opponent
                        else "No games synced yet.",
                        None,
                    )
                return build_full_game_detail_text(db, game, current_user.username), None

            content = ""
            for event in stream_coach_response_with_tools(
                final_messages, tools=[GET_GAME_DETAIL_TOOL], tool_handler=handle_global_tool_call
            ):
                if event["type"] == "text":
                    content += event["content"]
                    yield f"data: {json.dumps({'content': event['content']})}\n\n"

            chat_message = ChatMessage(
                user_id=current_user.id,
                conversation_id=conversation_id,
                role="assistant",
                content=content,
            )
            db.add(chat_message)
            db.commit()

            yield f"data: {json.dumps({'done': True})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
