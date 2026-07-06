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

import movie_db

load_dotenv()

app = FastAPI(title="Bollywood Dumb Charades")

SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

MIN_TEAMS = 2
MAX_TEAMS = 8
MIN_PLAYERS = 3
MAX_PLAYERS = 5

MOVIE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "year": {"type": "integer"},
        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard", "ultra_hard"]},
        "mime_hint": {"type": "string"},
        "min_mime_seconds": {"type": ["integer", "null"]},
    },
    "required": ["title", "year", "difficulty", "mime_hint", "min_mime_seconds"],
    "additionalProperties": False,
}


def online_mode_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def generate_online_movie(used_titles: List[str]) -> dict:
    """Ask Claude for one Bollywood movie to mime, live.

    Used only in online mode, as an alternative to sampling data/movies.db.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    avoid = ", ".join(used_titles) if used_titles else "none yet"
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=300,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": MOVIE_JSON_SCHEMA},
        },
        messages=[{
            "role": "user",
            "content": (
                "Suggest one real, well-known Bollywood movie for a game of dumb "
                "charades. Title length doesn't matter. Rate difficulty as "
                "easy/medium/hard/ultra_hard based on how concrete and "
                "recognizable it is once mimed. For hard or ultra_hard, also give "
                "min_mime_seconds (minimum seconds realistically needed to mime "
                "it out); otherwise min_mime_seconds must be null. "
                f"Do not suggest any of these already-used titles: {avoid}."
            ),
        }],
    )
    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    return {
        "id": movie_db.slugify(data["title"]),
        "title": data["title"],
        "year": data["year"],
        "difficulty": data["difficulty"],
        "mime_hint": data["mime_hint"],
        "min_mime_seconds": data["min_mime_seconds"],
    }


def pick_offline_movie(used_titles: List[str]) -> Optional[dict]:
    """Draw one random not-yet-used movie from data/movies.db.

    Called fresh on every /reveal (not pre-sampled at session start) so a
    session can run indefinitely without running out of a fixed-size pool.
    """
    available = [m for m in movie_db.all_movies() if m["title"] not in used_titles]
    if not available:
        return None
    m = random.choice(available)
    return {
        "id": m["id"],
        "title": m["title"],
        "year": m["year"],
        "difficulty": m["difficulty"],
        "mime_hint": m["mime_hint"],
        "min_mime_seconds": m["min_mime_seconds"],
    }


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


def new_state(participant_names: List[str], mode: str, movie_source: str) -> dict:
    teams = [{"id": f"t{i}", "name": name} for i, name in enumerate(participant_names)]
    return {
        "mode": mode,
        "movie_source": movie_source,
        "teams": teams,
        "scores": {t["id"]: 0 for t in teams},
        "turn_index": 0,
        "used_titles": [],
        "current": None,
        "pending_steal": False,
    }


def next_turn_index(state: dict) -> int:
    return (state["turn_index"] + 1) % len(state["teams"])


# ── Pydantic models ──────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    session_id: str
    teams: List[str]
    mode: str = "teams"  # "teams" | "individual"
    movie_source: str = "offline"  # "offline" | "online"


class ResolveRequest(BaseModel):
    result: str  # "correct" | "pass" | "steal_correct" | "steal_missed"
    guesser_id: Optional[str] = None  # required for "correct" in individual mode


# ── Routes ───────────────────────────────────────────────────────────────────

@app.post("/start")
async def start_game(req: StartRequest):
    mode = req.mode if req.mode in ("teams", "individual") else "teams"
    lo, hi = (MIN_TEAMS, MAX_TEAMS) if mode == "teams" else (MIN_PLAYERS, MAX_PLAYERS)
    if not (lo <= len(req.teams) <= hi):
        noun = "teams" if mode == "teams" else "players"
        raise HTTPException(
            status_code=400,
            detail=f"Need between {lo} and {hi} {noun}",
        )
    movie_source = req.movie_source if req.movie_source in ("offline", "online") else "offline"
    if movie_source == "online" and not online_mode_available():
        raise HTTPException(
            status_code=400,
            detail="Online mode requires ANTHROPIC_API_KEY to be configured",
        )
    label = "Team" if mode == "teams" else "Player"
    participant_names = [name.strip() or f"{label} {i + 1}" for i, name in enumerate(req.teams)]
    state = new_state(participant_names, mode, movie_source)
    save_session(req.session_id, state)
    return state


@app.get("/config")
async def get_config():
    return {"online_mode_available": online_mode_available()}


@app.get("/state/{session_id}")
async def get_state(session_id: str):
    state = load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No session found")
    return state


@app.post("/reveal/{session_id}")
async def reveal_movie(session_id: str):
    state = load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No session found")
    if state["current"] is not None:
        raise HTTPException(status_code=400, detail="A movie is already revealed")

    used_titles = state.setdefault("used_titles", [])
    if state.get("movie_source", "offline") == "online":
        try:
            movie = generate_online_movie(used_titles)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="Could not reach Claude to pick a movie. Try again.",
            )
    else:
        movie = pick_offline_movie(used_titles)
        if movie is None:
            raise HTTPException(status_code=400, detail="No movies left to pick from")

    state["current"] = movie
    used_titles.append(movie["title"])

    save_session(session_id, state)
    return state


@app.post("/resolve/{session_id}")
async def resolve_round(session_id: str, req: ResolveRequest):
    state = load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No session found")
    if state["current"] is None:
        raise HTTPException(status_code=400, detail="No movie is currently revealed")

    result = req.result
    turn = state["turn_index"]
    next_index = next_turn_index(state)

    if state.get("mode") == "individual":
        mimer_id = state["teams"][turn]["id"]
        if result == "correct":
            valid_ids = {t["id"] for t in state["teams"]}
            if not req.guesser_id or req.guesser_id not in valid_ids or req.guesser_id == mimer_id:
                raise HTTPException(
                    status_code=400,
                    detail="A valid guesser_id (not the mimer) is required",
                )
            state["scores"][mimer_id] += 1
            state["scores"][req.guesser_id] += 1
            state["current"] = None
            state["turn_index"] = next_index
        elif result == "pass":
            state["current"] = None
            state["turn_index"] = next_index
        else:
            raise HTTPException(status_code=400, detail="Unknown result")
    elif result == "correct":
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
