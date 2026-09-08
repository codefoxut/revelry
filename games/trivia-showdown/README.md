# Trivia Showdown

A browser-based, real-time multiplayer buzz-in trivia game — part of the Revelry
party-game collection. FastAPI + WebSockets backend, Next.js frontend.

## How to play

Whoever creates the room becomes the **host** — a non-competing screen everyone gathers
around. Every other player is a **contestant**, joining from their own phone as a buzzer.

- The host starts the game once at least one other player has joined. A random 10-question
  set is drawn from the question bank.
- When a question appears, contestants race to buzz in. First buzz locks out the rest until
  the question is resolved.
- The buzzed-in contestant answers out loud; the host judges it correct or incorrect.
  - Correct: 100 points, the answer is revealed, move on.
  - Incorrect: that contestant is locked out of the current question (but others can still
    buzz in), or if everyone's locked out, the answer is revealed automatically.
- The host can also reveal the answer directly at any time without waiting on a buzz.
- After the last question, whoever has the most points wins.

Talk it out face-to-face — voice/video happens outside the app, there's no in-app chat.

Needs at least 2 players (the host plus one contestant).

## Requirements

- Python 3.14+
- Node.js 24+
- Docker (only if running via Docker)

All commands below are run from this directory (`games/trivia-showdown/`).

## Quickest way to run it: Docker

```bash
make docker-build   # build backend + frontend images
make docker-up       # start both containers in the background
```

The app is then available at:

- Frontend: http://localhost:3300
- Backend: http://localhost:8300 (health check: http://localhost:8300/health)

```bash
make docker-logs     # tail logs from both containers
make docker-down     # stop and remove the containers
```

Trivia Showdown keeps all room/game state in memory — nothing persists across a backend
restart, so there's no database volume to worry about.

## Running locally without Docker

```bash
make install         # create backend .venv + pip install, npm install for frontend
make dev             # run backend (uvicorn --reload) and frontend (next dev) together
```

Or run each side on its own:

```bash
make dev-backend     # http://localhost:8300
make dev-frontend    # http://localhost:3300
```

## Running tests

```bash
make test            # backend (pytest) + frontend (vitest)
make test-backend
make test-frontend
```

## Configuration

The frontend reads `NEXT_PUBLIC_API_BASE_URL` / `NEXT_PUBLIC_WS_BASE_URL` (both default to
`localhost:8300`) — Next.js inlines these at build time, so when building your own Docker
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
