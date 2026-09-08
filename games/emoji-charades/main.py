import json
import os
import random
from pathlib import Path
from typing import List, Optional

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import emoji_db as db

load_dotenv()

app = FastAPI(title="Emoji Charades")

SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

MIN_TEAMS = 2
MAX_TEAMS = 8

_db_conn = db.get_connection()
if db.is_empty(_db_conn):
    # First run: seed the offline puzzle bank so the game is playable without
    # anyone remembering to run `make seed` first.
    import tools.seed_puzzles as seed_puzzles

    seed_puzzles.main()

PUZZLE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "clue": {"type": "string"},
        "answer": {"type": "string"},
    },
    "required": ["clue", "answer"],
    "additionalProperties": False,
}

CATEGORY_PROMPTS = {
    "movies": "a well-known movie title",
    "tv-shows": "a well-known TV show title",
    "phrases": "a common English idiom or phrase",
    "mixed": "a well-known movie title, TV show title, or common English idiom",
}


def online_mode_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def generate_online_puzzle(category_id: str, used_answers: List[str]) -> dict:
    """Ask Claude for one emoji puzzle, live.

    Used only in online mode, as an alternative to sampling data/puzzles.db.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    avoid = ", ".join(used_answers) if used_answers else "none yet"
    kind = CATEGORY_PROMPTS.get(category_id, CATEGORY_PROMPTS["mixed"])
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=300,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": PUZZLE_JSON_SCHEMA},
        },
        messages=[{
            "role": "user",
            "content": (
                f"Pick {kind} and encode it as a short sequence of 2-5 emoji "
                "(the 'clue') that a person could reasonably decode back to the "
                "original answer. Return the emoji clue and the plain-text answer. "
                f"Do not reuse any of these already-used answers: {avoid}."
            ),
        }],
    )
    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    return {"clue": data["clue"], "answer": data["answer"]}


def pick_offline_puzzle(category_id: str, used_answers: List[str]) -> Optional[dict]:
    conn = db.get_connection()
    puzzles = db.random_puzzles(conn, category_id, 1, exclude=used_answers)
    return puzzles[0] if puzzles else None


# ── Session helpers ──────────────────────────────────────────────────────────

def session_file(session_id: str) -> Path:
    safe = "".join(c for c in session_id if c.isalnum() or c == "-")
    return SESSIONS_DIR / f"{safe}.json"


def load_session(session_id: str) -> Optional[dict]:
    path = session_file(session_id)
    if path.exists():
        return json.loads(path.read_text())
    return None


def save_session(session_id: str, data: dict) -> None:
    session_file(session_id).write_text(json.dumps(data, indent=2))


def delete_session(session_id: str) -> None:
    path = session_file(session_id)
    if path.exists():
        path.unlink()


def new_state(team_names: List[str], category_id: str, source: str) -> dict:
    teams = [{"id": f"t{i}", "name": name} for i, name in enumerate(team_names)]
    return {
        "category": category_id,
        "source": source,
        "teams": teams,
        "scores": {t["id"]: 0 for t in teams},
        "turn_index": 0,
        "used_answers": [],
        "current": None,
        "pending_steal": False,
    }


def next_turn_index(state: dict) -> int:
    return (state["turn_index"] + 1) % len(state["teams"])


# ── Pydantic models ──────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    session_id: str
    teams: List[str]
    category: str = "mixed"
    source: str = "offline"  # "offline" | "online"


class ResolveRequest(BaseModel):
    result: str  # "correct" | "pass" | "steal_correct" | "steal_missed"


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/config")
async def get_config():
    return {"online_mode_available": online_mode_available()}


@app.get("/categories")
async def get_categories():
    conn = db.get_connection()
    categories = db.list_categories(conn)
    categories.append({"id": "mixed", "name": "Mixed", "emoji": "🎲", "color": "#7B2FF7"})
    return categories


@app.post("/start")
async def start_game(req: StartRequest):
    if not (MIN_TEAMS <= len(req.teams) <= MAX_TEAMS):
        raise HTTPException(
            status_code=400,
            detail=f"Need between {MIN_TEAMS} and {MAX_TEAMS} teams",
        )
    source = req.source if req.source in ("offline", "online") else "offline"
    if source == "online" and not online_mode_available():
        raise HTTPException(
            status_code=400,
            detail="Online mode requires ANTHROPIC_API_KEY to be configured",
        )
    conn = db.get_connection()
    if req.category != "mixed" and db.get_category(conn, req.category) is None:
        raise HTTPException(status_code=400, detail="Unknown category")
    team_names = [name.strip() or f"Team {i + 1}" for i, name in enumerate(req.teams)]
    state = new_state(team_names, req.category, source)
    save_session(req.session_id, state)
    return state


@app.get("/state/{session_id}")
async def get_state(session_id: str):
    state = load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No session found")
    return state


@app.post("/reveal/{session_id}")
async def reveal_puzzle(session_id: str):
    state = load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No session found")
    if state["current"] is not None:
        raise HTTPException(status_code=400, detail="A puzzle is already revealed")

    used_answers = state.setdefault("used_answers", [])
    if state.get("source", "offline") == "online":
        try:
            puzzle = generate_online_puzzle(state["category"], used_answers)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="Could not reach Claude to generate a puzzle. Try again.",
            )
    else:
        puzzle = pick_offline_puzzle(state["category"], used_answers)
        if puzzle is None:
            raise HTTPException(status_code=400, detail="No puzzles left to pick from")

    state["current"] = puzzle
    used_answers.append(puzzle["answer"])

    save_session(session_id, state)
    return state


@app.post("/resolve/{session_id}")
async def resolve_round(session_id: str, req: ResolveRequest):
    state = load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No session found")
    if state["current"] is None:
        raise HTTPException(status_code=400, detail="No puzzle is currently revealed")

    result = req.result
    turn = state["turn_index"]
    next_index = next_turn_index(state)

    if result == "correct":
        if state["pending_steal"]:
            raise HTTPException(status_code=400, detail="Resolve the steal first")
        state["scores"][state["teams"][turn]["id"]] += 1
        state["current"] = None
        state["turn_index"] = next_index
        state["pending_steal"] = False
    elif result == "pass":
        if state["pending_steal"]:
            raise HTTPException(status_code=400, detail="Already offered as a steal")
        state["pending_steal"] = True
    elif result == "steal_correct":
        if not state["pending_steal"]:
            raise HTTPException(status_code=400, detail="No steal is pending")
        state["scores"][state["teams"][next_index]["id"]] += 1
        state["current"] = None
        state["turn_index"] = next_index
        state["pending_steal"] = False
    elif result == "steal_missed":
        if not state["pending_steal"]:
            raise HTTPException(status_code=400, detail="No steal is pending")
        state["current"] = None
        state["turn_index"] = next_index
        state["pending_steal"] = False
    else:
        raise HTTPException(status_code=400, detail="Unknown result")

    save_session(session_id, state)
    return state


@app.post("/reset/{session_id}")
async def reset_session(session_id: str):
    delete_session(session_id)
    return {"status": "reset"}


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html") as f:
        return f.read()


app.mount("/static", StaticFiles(directory="static"), name="static")
