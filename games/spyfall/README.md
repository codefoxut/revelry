# Spyfall

A browser-based, real-time multiplayer Spyfall/Undercover game — part of the Revelry
party-game collection. FastAPI + WebSockets backend, Next.js frontend.

## How to play

Everyone but one secret spy is told the same secret location (airport, casino, submarine,
...) and given a role to play there (pilot, dealer, captain, ...). The spy is told nothing.
Players take turns asking each other in-character questions during the discussion window,
trying to work out who doesn't actually know the location — while the spy tries to blend in
and figure out the location from context.

- **Discussion**: talk it out face-to-face (voice/video happens outside the app — there's
  no in-app chat). A countdown timer auto-advances to voting when it runs out; the host can
  also advance manually at any time.
- **Voting**: everyone publicly votes for who they think the spy is. A clear plurality
  accuses that player and ends the game; a tie (or nobody voting) lets the spy evade.
- **The spy's escape hatch**: at any point during discussion or voting, the spy can guess
  the location instead of waiting to be voted out.

  > **Variant note**: this build makes a **wrong guess an instant loss for the spy** — the
  > game ends immediately either way. Classic Spyfall rulesets usually let a wrong guess
  > just fail silently so the spy can keep playing and try again later; we chose the
  > higher-stakes, simpler-to-implement version (every guess is final) as a deliberate
  > design choice, not an oversight.

Needs at least 3 players.

## Requirements

- Python 3.14+
- Node.js 24+
- Docker (only if running via Docker)

All commands below are run from this directory (`games/spyfall/`).

## Quickest way to run it: Docker

```bash
make docker-build   # build backend + frontend images
make docker-up       # start both containers in the background
```

The app is then available at:

- Frontend: http://localhost:3100
- Backend: http://localhost:8100 (health check: http://localhost:8100/health)

```bash
make docker-logs     # tail logs from both containers
make docker-down     # stop and remove the containers
```

Spyfall keeps all room/game state in memory — nothing persists across a backend restart,
so there's no database volume to worry about.

## Running locally without Docker

```bash
make install         # create backend .venv + pip install, npm install for frontend
make dev             # run backend (uvicorn --reload) and frontend (next dev) together
```

Or run each side on its own:

```bash
make dev-backend     # http://localhost:8100
make dev-frontend    # http://localhost:3100
```

## Running tests

```bash
make test            # backend (pytest) + frontend (vitest)
make test-backend
make test-frontend
```

## Configuration

The frontend reads `NEXT_PUBLIC_API_BASE_URL` / `NEXT_PUBLIC_WS_BASE_URL` (both default to
`localhost:8100`) — Next.js inlines these at build time, so when building your own Docker
image for a non-local deployment, pass them as build args (see `frontend/Dockerfile` and
`docker-compose.yml`).

The backend reads settings from environment variables prefixed `REVELRY_` (or a `.env`
file in `backend/`), see `backend/app/config.py` — notably `REVELRY_CORS_ORIGINS`.

## Project layout

```
backend/    FastAPI app (rooms, WebSocket gameplay, in-memory game state)
frontend/   Next.js app (lobby, in-game UI)
Makefile    dev / test / docker commands (see above)
docker-compose.yml
```
