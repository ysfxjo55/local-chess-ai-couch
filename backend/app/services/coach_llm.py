import json
from openai import OpenAI
from backend.app.config import settings

# The OpenAI Python SDK works unmodified against Gemini's OpenAI-compatible
# endpoint — same `tools`/`stream=True` calling convention — so switching
# providers is just a different base_url/key/model, not a rewrite. See
# config.py's LLM_PROVIDER for why Gemini (free tier) is the default.
if settings.LLM_PROVIDER == "gemini":
    # The SDK requires *some* non-empty api_key just to construct the
    # client — with no key configured yet, this used to raise at import
    # time and crash the entire app (auth, sync, stats, everything), not
    # just the coach feature. Fall back to a placeholder so only an actual
    # chat request fails (with a clear auth error from Gemini), not startup.
    client = OpenAI(
        api_key=settings.GEMINI_API_KEY or "unset-gemini-api-key",
        base_url=settings.GEMINI_BASE_URL,
    )
    MODEL = settings.GEMINI_MODEL
else:
    client = OpenAI(api_key=settings.OPENAI_API_KEY or "unset-openai-api-key")
    MODEL = settings.OPENAI_MODEL

# Lets the model ask the app to render a real chess diagram of a specific
# position, instead of trying to describe one in words. Only meaningful in
# the per-game chat, where there's an actual game (and its move list) to
# point into — the global chat has no single board to show.
SHOW_POSITION_TOOL = {
    "type": "function",
    "function": {
        "name": "show_position",
        "description": (
            "Show the user an interactive chess board of the position at a "
            "specific point in the game currently being discussed. Use this "
            "whenever you reference a specific move the user would benefit "
            "from actually seeing, not just reading about."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "move_number": {
                    "type": "integer",
                    "description": "The move number as it appears in the move list, e.g. 14 for \"Move 14 (White)\".",
                },
                "side": {
                    "type": "string",
                    "enum": ["White", "Black"],
                    "description": "Which side's move this is, matching the label, e.g. \"White\" for \"Move 14 (White)\".",
                },
                "caption": {
                    "type": "string",
                    "description": "Short caption for the diagram, e.g. \"Position after 13...Bg4\".",
                },
            },
            "required": ["move_number", "side"],
        },
    },
}

# Lets the global (cross-game) chat pull in one specific game's real move
# list on demand — without this, it only ever has summary-level stats
# (win rates, a handful of worst moves) and has to say "I can't see your
# moves" the moment the player asks about a particular game by name.
GET_GAME_DETAIL_TOOL = {
    "type": "function",
    "function": {
        "name": "get_game_detail",
        "description": (
            "Fetch the full move list and mistake analysis for one specific "
            "past game. Call this whenever the player references a "
            "particular game — by opponent name, \"my last game\", \"that "
            "game from last week\", etc — and you need actual move-by-move "
            "detail, not just the summary stats you already have."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "opponent": {
                    "type": "string",
                    "description": "The opponent's username, if the player named one. Omit entirely if they just mean their single most recent game.",
                },
            },
            "required": [],
        },
    },
}

SYSTEM_PROMPT = """
ROLE & PERSONA:
You are an expert, highly encouraging, and insightful English Chess Coach. Your mission is to help a beginner-level chess player improve by analyzing their post-game data. Your tone should be friendly, motivating, constructive, and educational—like a passionate grandmaster teaching a friend.

You are not a messenger relaying a separate engine's opinions — the evaluations, classifications, and best moves you're given ARE your own chess knowledge and perception, the same way a strong human player just sees that a move is a blunder without needing to cite a source. Never say "the engine suggests", "the engine wanted", "the engine preferred", "Stockfish found", or any phrasing that frames the analysis as something external you're reporting on. Say "the stronger move here was Nd5" or "this walks into a tactic", not "the engine says the stronger move was Nd5". This isn't just a wording swap — actually think and speak as the source of this judgment, the way Chess.com's or Lichess's own game-review bots do; they never cite themselves as a separate tool either.

CONTEXT & INPUT DATA SPECIFICATION:
You will receive GAME METADATA and a PRE-COMPUTED ANALYSIS SUMMARY (evaluations, move classifications, best-move alternatives). Treat this data as your own ground truth, not a third party's output you're allowed to second-guess or contradict — you must never recalculate, override, or cast doubt on it (and never show your internal reasoning — no "wait", "let me re-read", "correction"), but you also never attribute it to "the engine" out loud. It's simply what you know.

The player you are coaching is identified in GAME METADATA (player name, color, opponent, official result, and outcome). Always coach from THEIR perspective.

The PRE-COMPUTED ANALYSIS SUMMARY includes:
- Turning point: the single player move with the largest evaluation drop
- Classifications: Blunder (200+ cp lost), Mistake (80-199), Inaccuracy (30-79), Good, Excellent
- Stronger alternatives you'd have played instead, at moves where the player deviated from them

ANALYSIS GUIDELINES & TASKS:
1. Open by naming both players from metadata (e.g. "In your game against [Opponent] as [your color]...").
2. Focus your review on the turning point from the summary. Explain why that move was problematic in beginner-friendly chess terms.
3. Briefly mention other significant mistakes from the summary if relevant.
4. Give constructive advice: the underlying principle and what to focus on next time.
5. End with 2-3 short, actionable bullet tips derived from this game.

OUTPUT FORMAT REQUIREMENTS:
- Language: natural, fluent, engaging English.
- Use the opponent's username from metadata, not generic "your opponent".
- Ground every claim in the provided summary and metadata.
- Translate evaluation changes into human tactical and strategic language—no raw number crunching in the output.
- Keep the structure scannable with markdown headers and bullets.

VISUALS:
If a `show_position` tool is available to you, use it whenever you reference
a specific move the user would benefit from seeing on a real board — e.g.
the turning point, a blunder, or a position you're proposing an alternative
for. Don't narrate the board state in prose when you could show it instead.

LOOKING UP A SPECIFIC GAME:
If a `get_game_detail` tool is available to you, you're in the global chat,
where you normally only have summary-level stats, not any one game's actual
moves. The moment the player references a specific game — by opponent name,
"my last game", a date, etc — and wants real move-by-move detail (not just
"how did I do overall"), call this tool rather than saying you can't see
their moves or asking them to paste a PGN. You genuinely can look it up.

PERSONAL CONTEXT:
When a "This Player's All-Time Patterns" section is present, you're not
just analyzing one isolated game — you're their ongoing personal coach who
already knows their tendencies (win rate by color, which phase they blunder
in most, their common openings, their accuracy trend). Actually use it:
when a mistake in this game matches a pattern you already know about them,
say so plainly ("this is the same kind of endgame slip you've been making
lately") instead of treating every game as a first meeting. Don't force a
connection that isn't really there, and don't recite the stats back as a
list — reference them the way a coach who's watched all your games would,
naturally, in a sentence or two.

The rigid five-step structure above (turning point, other mistakes, advice,
bullet tips) is the shape of a first full review of a game, not a template
to repeat verbatim on every single reply in an ongoing conversation —
follow-up messages should just be a normal, natural conversation.
"""


def generate_analysis(messages: list[dict]) -> str:
    """Non-streaming call — the one-shot per-game coaching writeup."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.4,
    )
    return response.choices[0].message.content


TAKEAWAY_SYSTEM_PROMPT = """
You distill one lost chess game's analysis into exactly ONE memorable,
actionable rule — the single biggest recurring-pattern lesson from this
game, phrased as a concrete instruction the player can recognize and apply
in a future game, not a description of what happened in this one.

Bad (describes this game, not reusable): "You blundered your knight on
move 14 by moving it to f3."
Good (a reusable rule): "Before moving a knight to a square attacked by a
pawn, check whether that pawn is actually defended — don't assume it's
undefended just because no piece is guarding it directly."

Output ONLY the single rule sentence. No preamble, no markdown, no
quotation marks, no "Rule:" prefix, under 30 words.
"""


MOVE_EXPLANATION_SYSTEM_PROMPT = """
You explain ONE specific move from a chess game to the player who played it,
addressing them directly as "you". You're given the move they played, its
classification/centipawn loss, and the stronger move instead — treat these
as your own ground truth, not something to recalculate or attribute to "the
engine". Never say "the engine suggests" or similar.

Write 2-4 sentences: what was concretely wrong with the move they played
(what it missed, hung, or allowed), and what the stronger move accomplishes
instead. Be specific and concrete (name pieces/squares/threats), not a
generic platitude like "this move wasn't optimal". Talk ONLY about this one
moment, not the rest of the game. No markdown, no headers, plain prose.
"""


def generate_move_explanation(
    game_format: str, label: str, san: str, best_move: str | None,
    classification: str, cp_loss: int | None,
) -> str:
    """Short, single-move explanation — deliberately separate from
    generate_analysis (the whole-game writeup): a puzzle is quizzing one
    specific flagged move, which often isn't the game's single biggest
    turning point, so the explanation has to be scoped to that move alone."""
    prompt = (
        f"### Game\n{game_format}\n\n"
        f"### The move being reviewed\n"
        f"{label}: you played {san} ({classification}"
        + (f", lost {cp_loss}cp" if cp_loss is not None else "")
        + f")\n"
        + (f"Stronger move instead: {best_move}\n" if best_move else "")
    )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": MOVE_EXPLANATION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def generate_key_takeaway(game_format: str, analysis_summary: str) -> str:
    """Short, separate completion (not part of the full coaching writeup)
    — deliberately terse and low-temperature, since this gets stored
    permanently and re-injected into every future chat, unlike the
    one-off analysis prose."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": TAKEAWAY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"### Game Details\n{game_format}\n\n### Move Analysis Summary\n{analysis_summary}",
            },
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()


def stream_coach_response_with_tools(messages: list[dict], tools: list[dict], tool_handler):
    """
    Generic streaming call with tool-calling support — used by both the
    per-game chat (show_position) and the global chat (get_game_detail).

    `tool_handler(name, args) -> (result_text, event)`: resolves one tool
    call. `result_text` is fed back to the model as the tool's result (what
    it "sees"). `event`, if not None, is yielded to the caller for any
    UI-visible side effect the tool has — `show_position` reports its
    {ply, caption} this way; a tool with no UI effect (get_game_detail)
    just returns `event=None` and the data flows into the model's own
    following text instead.

    Yields:
      {"type": "text", "content": "..."}
      {"type": "tool", "name": "...", "event": {...}}   # only when event is not None

    Handles the full tool-call round-trip internally: stream the model's
    response, and if it calls a tool mid-stream, feed the result back and
    continue streaming its follow-up text — the caller only ever sees
    text/tool events, never the OpenAI-level plumbing.
    """
    working_messages = list(messages)

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=working_messages,
            temperature=0.4,
            stream=True,
            tools=tools,
        )

        text_buffer = ""
        tool_calls: dict[int, dict] = {}
        finish_reason = None

        for chunk in response:
            choice = chunk.choices[0]
            delta = choice.delta
            if choice.finish_reason:
                finish_reason = choice.finish_reason

            if delta.content:
                text_buffer += delta.content
                yield {"type": "text", "content": delta.content}

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    entry = tool_calls.setdefault(
                        tc.index, {"id": None, "name": "", "arguments": ""}
                    )
                    if tc.id:
                        entry["id"] = tc.id
                    if tc.function and tc.function.name:
                        entry["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        entry["arguments"] += tc.function.arguments

        if finish_reason != "tool_calls" or not tool_calls:
            return  # ordinary completion, nothing more to do

        # Replay the assistant's tool-call turn, then a synthetic tool
        # result per call, then loop back so the model can continue
        # narrating with the tool's (trivial) result in context.
        working_messages.append(
            {
                "role": "assistant",
                "content": text_buffer or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in tool_calls.values()
                ],
            }
        )

        for tc in tool_calls.values():
            try:
                args = json.loads(tc["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}

            result_text, event = tool_handler(tc["name"], args)
            if event is not None:
                yield {"type": "tool", "name": tc["name"], "event": event}

            working_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_text,
                }
            )
