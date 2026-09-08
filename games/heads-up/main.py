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

import heads_up_db as db

load_dotenv()

app = FastAPI(title="Heads Up!")

SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

MIN_TEAMS = 2
MAX_TEAMS = 8
MIN_ROUND_SECONDS = 30
MAX_ROUND_SECONDS = 120

_db_conn = db.get_connection()
if db.is_empty(_db_conn):
    # First run: seed the offline word bank so the game is playable without
    # anyone remembering to run `make seed` first.
    import tools.seed_categories as seed_categories

    seed_categories.main()

_SYSTEM_PROMPT = """\
You are crafting cards for "Heads Up!" — a party game where one player holds \
a phone to their forehead and teammates describe a word or phrase out loud \
(no gestures, no drawing) for them to guess before time runs out.

Golden rules for Heads Up items:
1. SPEAKABLE — teammates must be able to describe it verbally in a few words.
2. GUESSABLE — recognisable from a short spoken description alone, no visuals needed.
3. CONCRETE — prefer well-known specific things over vague abstractions.
4. SHORT — 1 to 4 words per item.
5. VARIED DIFFICULTY — mix easy, obvious items with a few trickier ones.

Output format: valid JSON array of strings, nothing else — no markdown, no prose."""

_USER_PROMPT_TEMPLATE = """\
Category: {category}
Number of items: {n}

Generate exactly {n} Heads Up items for this category. Avoid repeating any of \
these already-used items: {avoid}

Return ONLY a JSON array, e.g.: ["item one", "item two", "item three"]"""


def online_mode_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _fallback_words(category_id: str, n: int, exclude: List[str]) -> List[str]:
    words = db.random_items(_db_conn, category_id, n, exclude=exclude)
    if not words:
        # Word bank for this category is exhausted for this game — reuse
        # already-seen words rather than erroring out mid-party.
        words = db.random_items(_db_conn, category_id, n)
    return words


def generate_words(category_id: str, category_name: str, n: int, source: str, exclude: List[str]) -> List[str]:
    if source != "online" or not online_mode_available():
        return _fallback_words(category_id, n, exclude)

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    avoid = ", ".join(exclude[-40:]) if exclude else "none yet"
    prompt = _USER_PROMPT_TEMPLATE.format(category=category_name, n=n, avoid=avoid)
    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        words = json.loads(raw)
        if isinstance(words, list) and all(isinstance(w, str) for w in words) and words:
            return words[:n]
    except Exception as exc:
        print(f"[Claude] Word generation failed ({type(exc).__name__}): {exc}")

    return _fallback_words(category_id, n, exclude)


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


def leader(state: dict) -> Optional[str]:
    if not state["scores"]:
        return None
    return max(state["scores"], key=lambda team_id: state["scores"][team_id])


# ── Pydantic models ──────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    session_id: str
    teams: List[str]
    category_id: str = "mixed"
    word_source: str = "offline"  # "offline" | "online"
    round_seconds: int = 60
    target_score: Optional[int] = 20


class DeckRequest(BaseModel):
    count: int = 30


class ResolveRequest(BaseModel):
    correct: List[str] = []
    passed: List[str] = []


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/config")
async def get_config():
    return {"online_mode_available": online_mode_available()}


@app.get("/categories")
async def get_categories():
    categories = db.list_categories(_db_conn)
    categories.append({"id": "mixed", "name": "Mixed (all categories)", "emoji": "🎉", "color": "#FF6F91"})
    return {"categories": categories}


@app.post("/start")
async def start_game(req: StartRequest):
    if not (MIN_TEAMS <= len(req.teams) <= MAX_TEAMS):
        raise HTTPException(status_code=400, detail=f"Need between {MIN_TEAMS} and {MAX_TEAMS} teams")
    round_seconds = min(max(req.round_seconds, MIN_ROUND_SECONDS), MAX_ROUND_SECONDS)
    word_source = req.word_source if req.word_source in ("offline", "online") else "offline"
    if word_source == "online" and not online_mode_available():
        raise HTTPException(status_code=400, detail="Online mode requires ANTHROPIC_API_KEY to be configured")
    if req.category_id != "mixed" and db.get_category(_db_conn, req.category_id) is None:
        raise HTTPException(status_code=404, detail=f"Category '{req.category_id}' not found")

    team_names = [name.strip() or f"Team {i + 1}" for i, name in enumerate(req.teams)]
    teams = [{"id": f"t{i}", "name": name} for i, name in enumerate(team_names)]
    state = {
        "teams": teams,
        "scores": {t["id"]: 0 for t in teams},
        "turn_index": 0,
        "round_seconds": round_seconds,
        "target_score": req.target_score,
        "category_id": req.category_id,
        "word_source": word_source,
        "used_words": [],
        "game_over": False,
        "winner_id": None,
    }
    save_session(req.session_id, state)
    return state


@app.get("/state/{session_id}")
async def get_state(session_id: str):
    state = load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No session found")
    return state


@app.post("/deck/{session_id}")
async def get_deck(session_id: str, req: DeckRequest):
    state = load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No session found")
    if state["game_over"]:
        raise HTTPException(status_code=400, detail="Game is already over")

    category_id = state["category_id"]
    category_name = "Mixed" if category_id == "mixed" else db.get_category(_db_conn, category_id)["name"]
    count = max(5, min(req.count, 60))
    words = generate_words(category_id, category_name, count, state["word_source"], state["used_words"])
    random.shuffle(words)
    return {"words": words}


@app.post("/resolve/{session_id}")
async def resolve_turn(session_id: str, req: ResolveRequest):
    state = load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No session found")
    if state["game_over"]:
        raise HTTPException(status_code=400, detail="Game is already over")

    current_team = state["teams"][state["turn_index"]]
    state["scores"][current_team["id"]] += len(req.correct)
    state["used_words"].extend(req.correct)
    state["used_words"].extend(req.passed)
    state["turn_index"] = (state["turn_index"] + 1) % len(state["teams"])

    target = state["target_score"]
    if target and any(score >= target for score in state["scores"].values()):
        state["game_over"] = True
        state["winner_id"] = leader(state)

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
