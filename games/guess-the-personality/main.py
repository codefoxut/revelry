import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Guess the Personality")

SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT_TEMPLATE = """You are the host of "Guess the Personality" — a party quiz game.

## Teams
- **{TEAM_A}**
- **{TEAM_B}**

## Rules
1. On each team's turn, secretly pick ONE real, famous personality (actor, athlete,
   scientist, musician, historical figure, world leader, author, etc.) that you have
   not used yet this game.
2. Give **Clue #1** — cryptic and hard, no names, no direct giveaways.
3. The team gets exactly ONE guess per clue.
   - If they guess correctly: award points based on the clue number they guessed on —
     Clue 1 = 5 pts, Clue 2 = 4 pts, Clue 3 = 3 pts, Clue 4 = 2 pts, Clue 5 = 1 pt.
     Reveal the personality, congratulate them, update the scoreboard, and move to the
     other team's turn.
   - If they guess wrong, or ask for another clue: reveal the **next clue**, each one
     easier and more specific than the last (career highlights → distinctive traits →
     famous quote or associate → very on-the-nose hint).
   - If they still haven't guessed after **Clue 5**, reveal the answer, award 0 points,
     and move to the other team's turn.
4. Teams alternate turns after every round (correct guess, or exhausted clues).
5. Track the running score. First team to reach **15 points** wins the game — announce
   it with big celebration energy and stop giving new rounds.
6. Never reveal the personality's name or a synonym for it before the team either
   guesses correctly or exhausts all 5 clues.
7. Keep energy high — commentate like a quiz show host. Vary the categories of
   personalities across rounds (sports, cinema, science, history, music, politics).

## Language
Give every clue and every piece of commentary in **both English and Hindi**, every
single time — never one without the other. Format each bilingual line like this:

🔤 <the line in English>
🇮🇳 <the same line in Hindi, Devanagari script, natural conversational Hindi>

Keep the Hindi a faithful translation of the English (same meaning, same difficulty,
no extra hints). The **Score → ...** line itself stays exactly as shown below, with no
translation needed since it's just names and numbers.

## Start
Display the current score as:
**Score → {TEAM_A}: 0 | {TEAM_B}: 0**

Then ask (bilingually, per the format above): "Which team goes first — {TEAM_A} or
{TEAM_B}?\""""

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ── Session helpers ──────────────────────────────────────────────────────────

def session_file(session_id: str) -> Path:
    safe = "".join(c for c in session_id if c.isalnum() or c == "-")
    return SESSIONS_DIR / f"{safe}.json"


def load_session(session_id: str) -> dict:
    path = session_file(session_id)
    if path.exists():
        return json.loads(path.read_text())
    return {"team_a": "Team A", "team_b": "Team B", "messages": []}


def save_session(session_id: str, data: dict) -> None:
    session_file(session_id).write_text(json.dumps(data, indent=2))


def delete_session(session_id: str) -> None:
    path = session_file(session_id)
    if path.exists():
        path.unlink()


def build_prompt(team_a: str, team_b: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.replace("{TEAM_A}", team_a).replace("{TEAM_B}", team_b)


# ── Pydantic models ──────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    session_id: str
    team_a: str
    team_b: str


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    team_a: str
    team_b: str


# ── Routes ───────────────────────────────────────────────────────────────────

@app.post("/start", response_model=ChatResponse)
async def start_game(req: StartRequest):
    """Save team names and send the opening message to Claude."""
    team_a = req.team_a.strip() or "Team A"
    team_b = req.team_b.strip() or "Team B"

    data = {"team_a": team_a, "team_b": team_b, "messages": []}
    first_msg = f"Start the game! Teams are: {team_a} and {team_b}."
    data["messages"].append({"role": "user", "content": first_msg})

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        system=build_prompt(team_a, team_b),
        messages=data["messages"],
    )

    reply = response.content[0].text
    data["messages"].append({"role": "assistant", "content": reply})
    save_session(req.session_id, data)

    return ChatResponse(reply=reply, session_id=req.session_id, team_a=team_a, team_b=team_b)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    data = load_session(req.session_id)
    data["messages"].append({"role": "user", "content": req.message})

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        system=build_prompt(data["team_a"], data["team_b"]),
        messages=data["messages"],
    )

    reply = response.content[0].text
    data["messages"].append({"role": "assistant", "content": reply})
    save_session(req.session_id, data)

    return ChatResponse(
        reply=reply,
        session_id=req.session_id,
        team_a=data["team_a"],
        team_b=data["team_b"],
    )


@app.get("/history/{session_id}")
async def get_history(session_id: str):
    data = load_session(session_id)
    return {
        "team_a": data["team_a"],
        "team_b": data["team_b"],
        "messages": data["messages"],
    }


@app.post("/reset/{session_id}")
async def reset_session(session_id: str):
    delete_session(session_id)
    return {"status": "reset"}


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html") as f:
        return f.read()


app.mount("/static", StaticFiles(directory="static"), name="static")
