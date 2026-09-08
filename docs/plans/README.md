# Remaining games — execution plans

Seven games left on the roadmap (see the original 13-game plan for full
history). Each has its own plan file here, written so it can be picked up
and executed independently, in order, without re-deriving the design.

## Build order

| # | Game | Plan | Frontend port | Backend port |
|---|------|------|---------------|--------------|
| 1 | Would You Rather Live | [01-would-you-rather-live.md](01-would-you-rather-live.md) | 3400 | 8400 |
| 2 | Rapid Fire | [02-rapid-fire.md](02-rapid-fire.md) | 3500 | 8500 |
| 3 | Family Feud Live | [03-family-feud-live.md](03-family-feud-live.md) | 3600 | 8600 |
| 4 | Fill in the Blank | [04-fill-in-the-blank.md](04-fill-in-the-blank.md) | 3700 | 8700 |
| 5 | Wavelength | [05-wavelength.md](05-wavelength.md) | 3800 | 8800 |
| 6 | Scattergories Sprint | [06-scattergories-sprint.md](06-scattergories-sprint.md) | 3900 | 8900 |
| 7 | Two Truths and a Lie | [07-two-truths-and-a-lie.md](07-two-truths-and-a-lie.md) | 4100 | 9000 |

Port note: the natural next pair after Trivia Showdown's 3300/8300 would be
3400/8400 incrementing by 100 each game — followed for games 1–6. Game 7
would land on 4000/9000, but 4000 is the hub's own default port
(`HUB_PORT` in the root `Makefile`), so it's bumped to 4100 to avoid a
collision when the hub and all games run together.

## Shared architecture (applies to every game below)

Confirmed decisions from the original roadmap plan, unchanged:

- **Standalone fork per game** — each game gets its own full copy of the
  Mafia/Codenames/Trivia Showdown backend+frontend structure (own venv, own
  `npm install`, own ports, own `docker-compose.yml`). Not a shared
  platform.
- **Full production polish per game** — pytest + vitest coverage, Docker,
  `README.md`, root `Makefile` + `hub.py` wiring, root `README.md`
  checklist/table update. No "MVP first, harden later."

### What to fork verbatim (per game)

Backend (from `games/trivia-showdown/backend/` — the most recently built,
cleanest reference):
- `app/platform/room.py`, `room_manager.py`, `disconnect_grace.py`
- `app/websocket/connection_manager.py`, `dispatcher.py`
- `app/schemas/room.py`, `app/api/rooms.py`, `app/main.py`
- Only `app/games/<name>/` (`__init__.py`, `commands.py`, `events.py`,
  `phases.py`/state machine, `engine.py`, plus any content-bank module) and
  `app/schemas/ws_events.py` are genuinely game-specific and get rewritten
  per the plan below.

Frontend (from `games/trivia-showdown/frontend/`):
- `components/AvatarPicker.tsx`, `components/Spinner.tsx`, `lib/*`,
  `services/socket.ts` (+ its test), `app/globals.css`,
  `app/room/[code]/page.tsx`, all config files (`next.config.ts`,
  `eslint.config.mjs`, `postcss.config.mjs`, `tsconfig.json`,
  `vitest.config.ts`, `package.json` with name/ports adjusted), `Dockerfile`,
  `.dockerignore`, `.gitignore`, `AGENTS.md`, `CLAUDE.md`.
- Only `types/room.ts` (game_state shape), `types/ws-events.ts`,
  `services/api.ts` (`game_type` string), `store/roomStore.ts` (+ test),
  `features/room/LobbyView.tsx` (usually near-verbatim, tweak
  `MIN_PLAYERS_TO_START` + any lobby extras like team pick), and
  `features/room/GameView.tsx` (the fully game-specific component) are
  rewritten.
- ⚠️ Next.js 16.2.10 — read `node_modules/next/dist/docs/` before writing
  unfamiliar App Router code, per each fork's `AGENTS.md`.

Root wiring (same 3 edits every time):
- `Makefile`: add `<GAME>_FRONTEND_PORT`/`<GAME>_BACKEND_PORT` vars, append
  to `run`/`hub` targets' arg lists, add a `<game>:` target.
- `hub.py`: add a port arg + `build_games()` entry.
- `README.md`: flip the checklist item and add a Games-table row + a
  Quick-Start section.

### Standard definition of done (every game below)

- Playable end-to-end on desktop (≈1280×800) and mobile (≈390×844)
  viewports — verify with a scripted Playwright pass across host +
  ≥2 contestant browser contexts, plus a visual screenshot review, same
  approach used for Trivia Showdown.
- `pytest` (backend) and `npx vitest run` (frontend) both green.
- `npx tsc --noEmit` and `npx eslint .` clean.
- `docker-compose.yml` mirroring the existing games' pattern.
- Game's own `README.md` (how to play, ports, Docker + local dev commands,
  configuration, project layout).
- Root `Makefile` target + `hub.py` entry + root `README.md` checklist/table
  updated.
- Backend venv created fresh at `.venv` (not renamed from `venv` — avoids
  the stale-shebang bug hit during Trivia Showdown).

### Novel technical risks introduced across these 7 (flagged per-game below)

- **Team model** (Family Feud Live) — first game where players aren't a
  flat roster; needs a team-assignment step and team-scoped scoring/events.
- **Asymmetric/private state** (Wavelength, Two Truths and a Lie, and the
  submission phase of Fill in the Blank) — some data must go to one player
  only, not broadcast. Codenames' spymaster-only board view is the existing
  precedent for targeted (non-broadcast) sends via the connection manager;
  reuse that mechanism rather than inventing a new one.
- **Server-driven timers with auto-transition** (Rapid Fire's random-delay
  arm phase, Scattergories Sprint's countdown) — `disconnect_grace.py`
  already implements an asyncio-based delayed transition; follow that
  pattern instead of a new timer mechanism.
