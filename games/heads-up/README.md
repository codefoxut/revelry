# 🤳 Heads Up!

Category word game — hold the phone to your forehead, teammates describe the
word out loud (no gestures, no drawing), you guess before the timer runs out.
Single device passed around the group; no in-app chat, all the talking
happens face to face.

## How to play

1. Enter 2+ team names, pick a category, round length, and winning score.
2. Pass the phone to the first team's active player. They hold it up to
   their forehead (screen facing their teammates).
3. Teammates describe the word shown on screen. The holder tilts the phone
   forward when they get it right, tilts it back to pass — or just tap the
   **Got it / Pass** buttons if tilt isn't available (older phones, desktop,
   or no motion permission granted).
4. When the timer hits zero, the turn ends and the phone passes to the next
   team. First team to the target score wins.

## Setup

```bash
cd games/heads-up
echo "ANTHROPIC_API_KEY=your-key-here" > .env   # optional — enables AI-generated word packs
```

From the repo root: `make heads-up`. Or directly:

```bash
make install
make run
```

Open http://localhost:8082.

Tilt detection uses the Device Orientation API, which iOS Safari only
exposes after an explicit permission prompt (triggered by the "I'm Ready"
button) and only on secure origins (`localhost` counts; a phone on your
LAN needs HTTPS or a tunnel like `ngrok` to get the same prompt). The
on-screen buttons always work as a fallback.

## Word bank

Offline play draws from `data/categories.db`, a curated bank of ~250 terms
across 8 categories (seeded by `tools/seed_categories.py`, safe to re-run).
Online mode (toggle in setup, requires `ANTHROPIC_API_KEY`) asks Claude
Haiku for fresh terms per turn instead, falling back to the offline bank
silently if that call fails.

```bash
make seed   # (re)populate data/categories.db from the curated word list
```

## Commands

| Command      | What it does                                  |
|---------------|------------------------------------------------|
| `make install` | Create `.venv` and install dependencies        |
| `make run`     | Start the server with auto-reload (port 8082)  |
| `make seed`    | (Re)populate the offline word bank              |
| `make test`    | Run the pytest suite                            |
| `make clean`   | Remove `.venv` and caches                        |
