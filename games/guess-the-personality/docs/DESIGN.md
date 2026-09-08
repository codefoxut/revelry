# Guess the Personality — Design Document

A two-team party quiz game hosted entirely by Claude. Claude picks a real,
famous personality, gives progressively easier clues, scores guesses, and
tracks a running score across rounds — bilingually, in English and Hindi.

This document exists so the app can be picked up (or moved to another repo)
without prior conversation context.

## What this app is

- A single-page web app (`static/index.html`) talking to a small FastAPI
  backend (`main.py`).
- The game logic itself — writing clues, scoring, turn-taking, win
  condition — lives entirely in a system prompt handed to Claude on every
  turn. The backend does not implement any game rules; it is a thin,
  stateless-per-request relay that persists chat history.
- **Personality selection is DB-grounded, not invented.** Claude used to
  pick famous people purely from memory; it now only ever plays entries
  sampled from a real SQLite database (`data/personalities.db`, ~100k+
  Indian + ~100k+ additional non-Indian people, scraped from Wikidata) —
  see [`PERSONALITY_DATABASE.md`](PERSONALITY_DATABASE.md). Claude still
  writes the actual clues and hosts the show; it just can't invent a person
  or a fact about them that isn't in the sampled pool.

## Architecture

```
Browser (static/index.html)
   │  fetch() JSON over HTTP
   ▼
FastAPI (main.py)
   │  loads/saves session JSON       │  samples pool   │  anthropic SDK
   ▼                                  ▼                 ▼
sessions/<session_id>.json   data/personalities.db   Claude (claude-opus-4-8)
```

- **No server-side game state machine.** The backend never parses scores,
  clue numbers, or turns. It just appends the user's message, sends the
  whole transcript + system prompt to Claude, appends the reply, and saves.
  Claude re-derives "whose turn, what clue, what score" from re-reading the
  transcript each call. This part of the design is unchanged by the
  database — the DB only replaces *where the personalities and facts come
  from*, not how turns/scoring are tracked.
- **The personality pool is sampled once per game, not per round.** At
  `/start`, the backend samples ~50 people for the chosen `category`
  (`"india"` or `"world"`) from `personality_db.py` and stores that exact
  list in the session file as `personality_pool`. Every subsequent `/chat`
  call re-injects the *same* stored pool into the system prompt (via
  `{PERSONALITY_POOL}`) rather than resampling — the pool is the game's
  fixed "secret list" for its entire duration, the same way `used_titles`
  stays stable across a `bollywood-dumbcharades` session. Claude picks
  from that list, in any order, never repeating an entry, and never
  reveals the `Name` field before it's guessed or the clues run out.
- **Score display is a text convention, not structured data.** The system
  prompt requires Claude to emit a specific line — `**Score → {TEAM_A}: N |
  {TEAM_B}: N**` — and the frontend regex-matches that line out of the
  reply text to populate the score badge. If Claude ever drifts from this
  exact format, the score badge silently stops updating (chat still works).

## Backend (`main.py`)

### Session file format

```json
{
  "team_a": "Alpha",
  "team_b": "Beta",
  "category": "world",
  "personality_pool": [
    {"id": "q9682", "wikidata_qid": "Q9682", "name": "...", "is_indian": false,
     "nationality": "...", "occupation": "...", "gender": "...",
     "birth_year": 1946, "death_year": null, "description": "...", "sitelinks": 210}
  ],
  "messages": [
    {"role": "user", "content": "Start the game! Teams are: Alpha and Beta."},
    {"role": "assistant", "content": "..."}
  ]
}
```

`personality_pool` is written once at `/start` (sampled from
`data/personalities.db`, see [`PERSONALITY_DATABASE.md`](PERSONALITY_DATABASE.md))
and never regenerated for that session — `/chat` reads it back verbatim to
rebuild the system prompt each turn.

`session_file()` sanitizes the session id to `[A-Za-z0-9-]` before using it
as a filename — the only defense against path traversal via
`session_id`, since it comes straight from client-controlled JSON.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/` | Serves `static/index.html` |
| `POST` | `/start` | Body: `{session_id, team_a, team_b, category}` (`category` is `"india"` or `"world"`, default `"world"`). Samples a fresh `personality_pool` for that category, creates the session, sends the internal trigger message `"Start the game! Teams are: X and Y."`, returns Claude's opening reply. |
| `POST` | `/chat` | Body: `{session_id, message}`. Loads existing session (including its stored `personality_pool`), appends the user's message (a guess, "next clue", anything free-text), sends full history + system prompt to Claude, returns the reply. |
| `GET`  | `/history/{session_id}` | Returns `{team_a, team_b, category, messages}` — used on page load to restore an in-progress game. |
| `POST` | `/reset/{session_id}` | Deletes the session file. |

All chat-bearing responses share the `ChatResponse` shape:
`{reply, session_id, team_a, team_b, category}`.

### System prompt (`SYSTEM_PROMPT_TEMPLATE`)

Built once per request via `build_prompt(team_a, team_b, personality_pool)`,
which does a plain `str.replace` on `{TEAM_A}` / `{TEAM_B}` /
`{PERSONALITY_POOL}` placeholders — no Jinja/f-string, so literal `{`/`}`
elsewhere in the template must be avoided or escaped. `{PERSONALITY_POOL}`
is filled in by `format_personality_pool()`, which renders each sampled row
as a `- Name: ... | Facts: ...` bullet.

Game rules encoded in the prompt (see `main.py` for exact wording):

- Claude picks one entry per round from the secret `{PERSONALITY_POOL}`
  list only — never invented, never reused within the same game — and
  writes clues strictly from that entry's `Facts` (no outside trivia).
- Up to **5 clues**, cryptic → obvious. **One guess per clue.**
- Scoring: correct on clue 1–5 → 5/4/3/2/1 points; still wrong after clue 5
  → 0 points, personality revealed, move on.
- Teams alternate turns after every round.
- First to **15 points** wins; Claude is told to stop the game at that point.
- **Bilingual output is mandatory**: every clue and every piece of host
  commentary must be given in English and Hindi together, one line each,
  formatted as:
  ```
  🔤 <English>
  🇮🇳 <Hindi, Devanagari script>
  ```
  The `**Score → ...**` line itself is exempt from translation (it's just
  names/numbers) — this keeps the frontend's score regex reliable.

This is **not user-configurable at runtime** — there is no language toggle;
bilingual is baked into the prompt as the only mode.

### Model

Hardcoded as `"claude-opus-4-8"` in both `/start` and `/chat`, `max_tokens=1024`.
No streaming — the frontend shows a typing indicator and waits for the full
response.

## Frontend (`static/index.html`)

Single file: inline `<style>` + inline `<script>`, no build step, no
framework, no external JS/CSS dependencies.

- **Session identity**: a v4-ish UUID generated client-side
  (`newUUID()`), cached in `localStorage['gtp_session_id']`. Team names
  are cached in `localStorage['gtp_team_a'/'gtp_team_b']` purely for
  pre-filling the "New Game" modal — the source of truth for team names is
  always the backend session.
- **Category selector**: the setup modal has a World/Indian-only toggle
  (`selectCategory()`), sent as `category` on `POST /start` and cached in
  `localStorage['gtp_category']` purely to pre-select it on the next "New
  Game" — same treatment as team names, backend session is still the
  source of truth.
- **Page load flow**: fetch `/history/{sessionId}` →
  - messages exist → replay them into the chat log, restore `category`,
    skip the internal `"Start the game!"` trigger message, hide the setup
    modal.
  - no messages → show the team-name/category setup modal.
- **Sending a message**: `sendMessage()` → optimistically renders the
  user's bubble → `POST /chat` → renders Claude's reply. Score badge is
  updated by regex-scanning the reply text (`extractScore()`) for the
  `Score → A: n | B: n` line.
- **Markdown**: a hand-rolled `parseMarkdown()` handles only `**bold**`,
  `_italic_`, and `\n` → `<br>` (after HTML-escaping). Anything else Claude
  emits (headers, lists, etc.) renders as literal text — the system prompt
  intentionally sticks to bold/italic/newlines for this reason.
- **New Game**: `POST /reset/{sessionId}`, mint a new UUID, clear the chat
  DOM, reopen the modal.
- No timer/clock UI (unlike the sibling `bollywood-dumbcharades` app,
  which mimes against a countdown) — this game is guess-driven, not
  time-driven.

## Config, deployment, dependencies

- `requirements.txt`: `fastapi[all]`, `anthropic`, `uvicorn[standard]`,
  `python-dotenv`, `requests` (the last one only used by
  `tools/scrape_wikidata_personalities.py`, not by gameplay itself).
- `.env` (gitignored) must contain `ANTHROPIC_API_KEY=...`.
- `Makefile` targets: `setup` (create `.venv`, idempotent via the
  `.venv/bin/activate` file target), `install` (depends on `setup`, then
  `pip install -r requirements.txt`), `run` (depends on `install`, then
  `uvicorn main:app --port 8081 --reload`), `clean`.
- Port `8081` (chosen to avoid clashing with `bollywood-dumbcharades` on
  `8080` when both run on the same machine) — arbitrary, change freely.
- `sessions/` (gitignored) is created at import time
  (`SESSIONS_DIR.mkdir(exist_ok=True)`) relative to the process's current
  working directory — `main.py` must be run from the project root (which
  `make run` does implicitly, since Make runs from the Makefile's
  directory).
- There used to be a `run.sh` entrypoint that ran against a hardcoded
  external venv (`/Users/ujjwal/bigjobs/pipecat/.venv`) borrowed from an
  unrelated local project, purely as a shortcut to skip venv setup. It has
  been removed — `make setup && make install && make run` is the only
  supported way to run this app now, and it's portable to any machine.

## Moving this to another repo — checklist

1. Copy `main.py`, `personality_db.py`, `static/index.html`,
   `requirements.txt`, `Makefile`, `.gitignore`, and `data/personalities.db`
   (the populated database itself — see
   [`PERSONALITY_DATABASE.md`](PERSONALITY_DATABASE.md); without it the app
   still runs but every category samples zero personalities).
2. Recreate `.env` with a valid `ANTHROPIC_API_KEY` — it's gitignored, so
   it won't come along in a copy/git-mv.
3. `sessions/` and `.venv/` are gitignored and regenerate on first run —
   nothing to migrate there.
4. This app now has one piece of intra-repo-style coupling: `main.py`
   imports `personality_db.py` (same pattern as
   `bollywood-dumbcharades`/`movie_db.py`) — both files must travel
   together.
5. Decide on a port if running alongside other local apps.

## Known limitations / things to watch

- **No real turn/score enforcement.** Everything (whose turn it is, the
  running score, which clue number we're on) is inferred by Claude from
  re-reading the transcript each call. A model slip (wrong arithmetic,
  forgetting whose turn it is, drifting score format) is not caught or
  corrected by the backend — there's no validation layer.
- **Score badge is regex-fragile.** `extractScore()` in the frontend
  depends on Claude emitting the exact `Score → A: n | B: n` shape. If the
  system prompt is edited and that instruction is weakened, the badge
  quietly stops updating (the chat itself keeps working).
- **Unbounded session growth.** The full message transcript is resent to
  Claude on every turn with no truncation/summarization — a very long game
  (many rounds) grows the request payload and cost linearly with turns.
- **No auth.** Any client with a `session_id` can `POST /chat` to that
  session — fine for a local party-game use case, not suitable as-is for a
  multi-tenant public deployment.
- **`session_id` sanitization** strips to `[A-Za-z0-9-]` before touching
  the filesystem, but there's no rate limiting or size cap on `message` —
  a malicious client could send arbitrarily large messages to run up API
  cost.
- **Fixed pool per game.** The ~50-person `personality_pool` sampled at
  `/start` is the entire universe of people playable for that session —
  if the game somehow runs past 50 rounds without Claude noticing it's
  exhausted the list, there's no fallback (no re-sampling mid-game, by
  design — see the Architecture section above).
- **India category is capped by real-world data, not code.** Wikidata has
  roughly 94-95k humans with India listed as country of citizenship total
  — `--target 100000` on `--category india` will plateau there rather than
  reach 100k; the `world` category (occupation-scoped, no citizenship
  filter) has no such ceiling. See
  [`PERSONALITY_DATABASE.md`](PERSONALITY_DATABASE.md).
