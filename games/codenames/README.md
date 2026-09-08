# Codenames

A browser-based, real-time multiplayer Codenames game — part of the Revelry party-game
collection. FastAPI + WebSockets backend, Next.js frontend.

## How to play

Players split into a red team and a blue team, each with one secret **spymaster**. A
shared 25-word board is dealt, with each word secretly colored red, blue, neutral, or the
single black **assassin** — only the two spymasters can see the colors.

- On your team's turn, your spymaster gives a one-word clue plus a number, meaning "this
  many of our words relate to this clue."
- Your **guessers** then click cards trying to find your team's words. A correct guess lets
  you keep guessing (up to number + 1 total); a wrong guess (neutral or the other team's
  word) ends your turn immediately.
- Guess the assassin and your team loses instantly, no matter how many words you'd already
  found.
- First team to find all of their words wins.

Talk it out face-to-face — voice/video happens outside the app, there's no in-app chat.

Needs at least 4 players (so each team has both a spymaster and at least one guesser).

## Requirements

- Python 3.14+
- Node.js 24+
- Docker (only if running via Docker)

All commands below are run from this directory (`games/codenames/`).

## Quickest way to run it: Docker

```bash
make docker-build   # build backend + frontend images
make docker-up       # start both containers in the background
```

The app is then available at:

- Frontend: http://localhost:3200
- Backend: http://localhost:8200 (health check: http://localhost:8200/health)

```bash
make docker-logs     # tail logs from both containers
make docker-down     # stop and remove the containers
```

Codenames keeps all room/game state in memory — nothing persists across a backend
restart, so there's no database volume to worry about.

## Running locally without Docker

```bash
make install         # create backend .venv + pip install, npm install for frontend
make dev             # run backend (uvicorn --reload) and frontend (next dev) together
```

Or run each side on its own:

```bash
make dev-backend     # http://localhost:8200
make dev-frontend    # http://localhost:3200
```

## Running tests

```bash
make test            # backend (pytest) + frontend (vitest)
make test-backend
make test-frontend
```

## Configuration

The frontend reads `NEXT_PUBLIC_API_BASE_URL` / `NEXT_PUBLIC_WS_BASE_URL` (both default to
`localhost:8200`) — Next.js inlines these at build time, so when building your own Docker
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
