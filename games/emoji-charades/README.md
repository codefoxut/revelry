# 😀 Emoji Charades

Guess the movie, TV show, or phrase from an emoji clue — single screen,
teams take turns shouting out guesses. No miming, no drawing: the whole
group looks at the phone/screen together and races to decode it.

## How to play

1. Enter 2+ team names, pick a category, and a puzzle source.
2. The active team's turn starts. Tap **Reveal Puzzle** to show the emoji
   clue to everyone.
3. Shout out guesses. Tap **Got it!** to score a point, or **Pass** to hand
   the same clue to the next team as a steal chance.
4. Play continues turn by turn — tap **End Game** any time to see the final
   scoreboard.

## Setup

```bash
cd games/emoji-charades
echo "ANTHROPIC_API_KEY=your-key-here" > .env   # optional — enables AI-generated puzzles
```

From the repo root: `make emoji-charades`. Or directly:

```bash
make install
make run
```

Open http://localhost:8083.

## Puzzle bank

Offline play draws from `data/puzzles.db`, a curated bank of ~65 emoji
puzzles across movies, TV shows, and phrases/idioms (seeded by
`tools/seed_puzzles.py`, safe to re-run). Online mode (toggle in setup,
requires `ANTHROPIC_API_KEY`) asks Claude for a fresh emoji-encoded puzzle
each turn instead, falling back silently to the offline bank if that call
fails.

```bash
make seed   # (re)populate data/puzzles.db from the curated puzzle list
```

## Commands

| Command      | What it does                                  |
|---------------|------------------------------------------------|
| `make install` | Create `.venv` and install dependencies        |
| `make run`     | Start the server with auto-reload (port 8083)  |
| `make seed`    | (Re)populate the offline puzzle bank            |
| `make test`    | Run the pytest suite                            |
| `make clean`   | Remove `.venv` and caches                        |
