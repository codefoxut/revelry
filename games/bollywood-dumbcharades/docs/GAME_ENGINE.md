# Game engine

This file documents how the game itself (session state, scoring, turn
rotation, the two play modes) works, so any LLM or human picking this
project up later can extend it correctly without prior conversation
context. For how the movie list is stored/grown, see
[`MOVIE_DATABASE.md`](MOVIE_DATABASE.md).

## Architecture in one paragraph

`main.py` is a FastAPI app that owns all game state server-side —
`static/index.html` is a single vanilla-JS file with no framework and no
client-side state beyond the DOM and two `localStorage` keys. Every score,
turn, and round outcome lives in a JSON file per session
(`sessions/<id>.json`, gitignored) and every state-changing action is a
`POST` that returns the new full state, which the frontend renders
wholesale via `renderState(state)`. There is no partial/incremental DOM
diffing — each render replaces `#stage` and `#actions` innerHTML from
scratch. This matters if you're tempted to add client-only state: don't —
anything that needs to survive a page refresh or be consistent across
players' phones must go through the server.

## Session state shape

```jsonc
{
  "mode": "teams" | "individual",
  "teams": [{ "id": "t0", "name": "Red Squad" }, ...],   // "teams" list holds
                                                          // players too in
                                                          // individual mode —
                                                          // same shape either way
  "scores": { "t0": 0, "t1": 1, ... },
  "turn_index": 0,               // index into `teams` of whoever is up
  "pool": [ {id, title, year, difficulty, mime_hint}, ... ],  // remaining movies
  "current": { ... } | null,     // the currently revealed movie, or null
  "pending_steal": false,        // teams mode only — see below
  "status": "playing" | "finished",
  "winner": "t1" | null          // team/player id once status is "finished"
}
```

Persisted verbatim as pretty-printed JSON by `save_session`/`load_session`
in `main.py`. There's no schema migration — if you add a field, give it a
default via `.get()` on read paths (see `state.get("mode")` in
`resolve_round`) so old session files on disk don't 500.

## The two modes

Added to let 3-5 people play without enough bodies to split into teams —
mirrors the same two-mode split used in `simple-tornado/pictionary`.

### Teams mode (`mode: "teams"`, 2-8 teams)

One team mimes, the rest guess as a group. Unchanged from the original
design:

- **Correct** → the miming team gets +1, turn passes to the next team.
- **Pass** → sets `pending_steal = true` instead of advancing the turn.
  The *next* team in rotation (not the whole room) gets one shot to
  steal the point:
  - **They got it!** (`steal_correct`) → that next team gets +1, turn
    moves past them.
  - **Nobody got it** (`steal_missed`) → no one scores, turn still moves
    past them.

### Individual mode (`mode: "individual"`, 3-5 players)

One person mimes each round; there's no team to absorb a wrong guess, so
there's deliberately **no steal mechanic** here — "pass" just means
nobody in the room got it, and turn moves on with no score. The
interesting case is a correct guess:

- **Correct** → the frontend shows a "Who guessed it?" picker listing
  every player except the current mimer (a plain client-side render —
  see `renderGuesserPicker` in `static/index.html` — not a server round
  trip). Whoever's tapped becomes `guesser_id` on the `/resolve` call.
  The backend then awards **+1 to both the mimer and the guesser** in
  the same request. This is the whole point of the mode: two people
  score per correct round instead of one.

Both modes share `turn_index` rotation, `WIN_SCORE = 10` win-checking,
and the same movie pool/reveal flow — only the resolve-endpoint branch
and the setup-screen bounds differ. See `MODE_LIMITS` in
`static/index.html` and the `mode ==` branches in `resolve_round()` in
`main.py` if you need to adjust bounds or add a third mode.

## API surface (`main.py`)

| Route | Method | Purpose |
|---|---|---|
| `/start` | POST | `{session_id, teams: [names], mode}` → creates a fresh session, samples a movie pool, returns initial state. `teams` holds names for either mode (bad naming carried over from the teams-only original — treat it as "participant names" regardless of mode). |
| `/state/{id}` | GET | Fetch current state; 404 if the session doesn't exist yet (frontend uses the 404 to decide whether to show the setup modal on load). |
| `/reveal/{id}` | POST | Pops the next movie off `pool` into `current`. 400 if one's already revealed or the pool's empty. |
| `/resolve/{id}` | POST | `{result, guesser_id?}` — see mode branches above. Always calls `apply_win_check` and re-saves. |
| `/reset/{id}` | POST | Deletes the session file. Frontend then mints a new `session_id` and shows the modal again. |

`ResolveRequest.result` values: `"correct"`, `"pass"` (both modes);
`"steal_correct"`, `"steal_missed"` (teams mode only — sending these in
individual mode hits the `else: raise HTTPException` in that branch).

## Frontend (`static/index.html`)

No build step, no framework — a single `<script>` block manipulating the
DOM directly by element id (`stageEl`, `actionsEl`, `bannerEl`, etc.) and
template-string `innerHTML`. Key entry points if you're extending this:

- `renderState(state)` — the one function that redraws everything after
  any server response. Always sets `currentState = state` first; other
  functions (like `onCorrectClick`) read that global rather than
  threading state through every call.
- `MODE_LIMITS` — per-mode `{min, max, label, placeholder}` driving the
  setup modal's add/remove bounds and copy. Add a new mode here plus a
  matching backend branch, not a parallel set of constants.
- `buildTeamRows`/`addTeamRow`/`removeTeamRow` — generic over
  `currentMode`; despite the name they render whatever `MODE_LIMITS`
  says (teams or players).
- `onCorrectClick` / `renderGuesserPicker` — the individual-mode-only
  client-side interstitial described above. `resolve(result, guesserId)`
  is the one function that actually calls `/resolve`.
- `currentMode` and `lastTeamNames` persist across reloads via
  `localStorage` (`dc_mode`, `dc_team_names`); `sessionId` similarly via
  `dc_session_id` so an in-progress game survives a refresh.

## Local dev

```bash
make install   # creates .venv, installs requirements.txt
make run       # requires a .env with ANTHROPIC_API_KEY (only used by
               # tools/ scripts, not needed for gameplay itself), serves
               # on :8080 with --reload
```

`ANTHROPIC_API_KEY` is only read by the offline curation scripts in
`tools/` (see `MOVIE_DATABASE.md`) — gameplay itself never calls an LLM,
so the server runs fine without a real key if you're only testing game
logic. `sessions/` and `.venv/` are gitignored; deleting `sessions/`
while the server is running will 500 the next write until the directory
exists again (it's only `mkdir`'d once, at import time, in `main.py`).
