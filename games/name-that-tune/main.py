import json
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import tunes_db as db

app = FastAPI(title="Name That Tune")

SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

MIN_TEAMS = 2
MAX_TEAMS = 8

_db_conn = db.get_connection()
if db.is_empty(_db_conn):
    # First run: seed the melody bank so the game is playable without anyone
    # remembering to run `make seed` first.
    import tools.seed_tunes as seed_tunes

    seed_tunes.main()


def pick_tune(category_id: str, used_titles: List[str]) -> Optional[dict]:
    conn = db.get_connection()
    return db.random_tune(conn, category_id, exclude=used_titles)


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


def new_state(team_names: List[str], category_id: str) -> dict:
    teams = [{"id": f"t{i}", "name": name} for i, name in enumerate(team_names)]
    return {
        "category": category_id,
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
    category: str = "mixed"


class ResolveRequest(BaseModel):
    result: str  # "correct" | "pass" | "steal_correct" | "steal_missed"


# ── Routes ───────────────────────────────────────────────────────────────────

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
    conn = db.get_connection()
    if req.category != "mixed" and db.get_category(conn, req.category) is None:
        raise HTTPException(status_code=400, detail="Unknown category")
    team_names = [name.strip() or f"Team {i + 1}" for i, name in enumerate(req.teams)]
    state = new_state(team_names, req.category)
    save_session(req.session_id, state)
    return state


@app.get("/state/{session_id}")
async def get_state(session_id: str):
    state = load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No session found")
    return state


@app.post("/reveal/{session_id}")
async def reveal_tune(session_id: str):
    state = load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No session found")
    if state["current"] is not None:
        raise HTTPException(status_code=400, detail="A tune is already revealed")

    used_titles = state.setdefault("used_titles", [])
    tune = pick_tune(state["category"], used_titles)
    if tune is None:
        raise HTTPException(status_code=400, detail="No tunes left to pick from")

    state["current"] = tune
    used_titles.append(tune["title"])

    save_session(session_id, state)
    return state


@app.post("/resolve/{session_id}")
async def resolve_round(session_id: str, req: ResolveRequest):
    state = load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No session found")
    if state["current"] is None:
        raise HTTPException(status_code=400, detail="No tune is currently revealed")

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
