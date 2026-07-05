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

MOVIE_POOL_SIZE = 30
WIN_SCORE = 10
MIN_TEAMS = 2
MAX_TEAMS = 8
MIN_PLAYERS = 3
MAX_PLAYERS = 5

MOVIE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "year": {"type": "integer"},
        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
        "mime_hint": {"type": "string"},
    },
    "required": ["title", "year", "difficulty", "mime_hint"],
    "additionalProperties": False,
}


def online_mode_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def generate_online_movie(used_titles: List[str]) -> dict:
    """Ask Claude for one dumb-charades-ready Bollywood movie, live.

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
                "Suggest one real Bollywood movie for a game of dumb charades. "
                "It must be short/iconic enough to mime in under a minute, have "
                "a concrete recognizable object/action/scene, and be well known. "
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
    }


def sample_movie_pool(limit: int = MOVIE_POOL_SIZE) -> List[dict]:
    """Pick a shuffled set of mimeable movies for one game session.

    Sampled once at session start so the pool stays stable for the whole game.
    """
    ready = movie_db.ready_movies()
    chosen = random.sample(ready, min(limit, len(ready)))
    return [
        {
            "id": m["id"],
            "title": m["title"],
            "year": m["year"],
            "difficulty": m["difficulty"],
            "mime_hint": m["mime_hint"],
        }
        for m in chosen
    ]


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
        "pool": sample_movie_pool() if movie_source == "offline" else [],
        "used_titles": [],
        "current": None,
        "pending_steal": False,
        "status": "playing",
        "winner": None,
    }


def next_turn_index(state: dict) -> int:
    return (state["turn_index"] + 1) % len(state["teams"])


def apply_win_check(state: dict) -> None:
    for team in state["teams"]:
        if state["scores"][team["id"]] >= WIN_SCORE:
            state["status"] = "finished"
            state["winner"] = team["id"]
            return


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
    if state["status"] != "playing":
        raise HTTPException(status_code=400, detail="Game already finished")
    if state["current"] is not None:
        raise HTTPException(status_code=400, detail="A movie is already revealed")

    if state.get("movie_source", "offline") == "online":
        try:
            movie = generate_online_movie(state.get("used_titles", []))
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="Could not reach Claude to pick a movie. Try again.",
            )
        state["current"] = movie
        state.setdefault("used_titles", []).append(movie["title"])
    else:
        if not state["pool"]:
            raise HTTPException(status_code=400, detail="No movies left in the pool")
        state["current"] = state["pool"].pop(0)

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

    apply_win_check(state)
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
