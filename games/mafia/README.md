# Mafia

A browser-based, real-time multiplayer Mafia game — part of the Revelry party-game
collection. FastAPI + WebSockets backend, Next.js frontend.

## Requirements

- Python 3.14+
- Node.js 24+
- Docker (only if running via Docker)

All commands below are run from this directory (`games/mafia/`).

## Quickest way to run it: Docker

```bash
make docker-build   # build backend + frontend images
make docker-up       # start both containers in the background
```

The app is then available at:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000 (health check: http://localhost:8000/health)

```bash
make docker-logs     # tail logs from both containers
make docker-down     # stop and remove the containers
```

Game data (SQLite) persists across restarts in a named Docker volume.

## Running locally without Docker

```bash
make install         # create backend .venv + pip install, npm install for frontend
make dev             # run backend (uvicorn --reload) and frontend (next dev) together
```

Or run each side on its own:

```bash
make dev-backend     # http://localhost:8000
make dev-frontend    # http://localhost:3000
```

## Running tests

```bash
make test            # backend (pytest) + frontend (vitest)
make test-backend
make test-frontend
```

## Configuration

The frontend reads `NEXT_PUBLIC_API_BASE_URL` / `NEXT_PUBLIC_WS_BASE_URL` (both default to
`localhost:8000`) — Next.js inlines these at build time, so when building your own Docker
image for a non-local deployment, pass them as build args (see `frontend/Dockerfile` and
`docker-compose.yml`).

The backend reads settings from environment variables prefixed `REVELRY_` (or a `.env`
file in `backend/`), see `backend/app/config.py` — notably `REVELRY_CORS_ORIGINS` and
`REVELRY_DATABASE_URL`.

## Project layout

```
backend/    FastAPI app (rooms, WebSocket gameplay, SQLite persistence)
frontend/   Next.js app (lobby, in-game UI)
Makefile    dev / test / docker commands (see above)
docker-compose.yml
```
