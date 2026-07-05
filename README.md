# Revelry 🎉

Modern party games for friends, families, and teams.

## Features

- Browser-based
- Real-time multiplayer
- Mobile friendly
- AI-powered game generation
- No downloads required

## Tech Stack

- Next.js, React, TypeScript, Tailwind CSS (frontend)
- FastAPI, SQLAlchemy, WebSockets (backend)
- SQLite (persistent data) + in-memory stores (active game state)

## Roadmap

- [ ] Game Rooms
- [ ] Authentication
- [ ] Guess the Word
- [x] Charades
- [x] Mafia
- [x] Pictionary
- [x] Guess the Personality
- [ ] Trivia
- [ ] AI Host


## Games

⬜ Guess the Word
✅ Charades
⬜ Truth or Dare
⬜ Heads Up
✅ Pictionary
✅ Mafia
✅ Guess the Personality
⬜ Codenames
⬜ Would You Rather
⬜ Trivia
⬜ Two Truths and a Lie
⬜ Rapid Fire

## Quick Start

### [Games Hub](hub.py)

A single landing page linking to whichever games are currently running (and
showing the start command for the rest). Dependency-free — stdlib only, so
there's nothing to install.

```bash
make run
```

Starts the hub and opens it at http://localhost:4000. Use `make hub` to start
it without opening a browser, or `make open` to open it again from a second
terminal.

### [Mafia](games/mafia/README.md)

Real-time multiplayer, browser-based.

From the repo root: `make mafia`. Or directly:

```bash
cd games/mafia
make install && make dev
```

Open http://localhost:3000 (backend runs on http://localhost:8000). See the
[game's README](games/mafia/README.md) for the Docker-based alternative and full command
list.

### [Charades](games/bollywood-dumbcharades)

Bollywood-movie charades, single screen, AI-powered clue generation.

```bash
cd games/bollywood-dumbcharades
echo "ANTHROPIC_API_KEY=your-key-here" > .env
```

Then from the repo root: `make charades`. Or directly: `make run`.

Open http://localhost:8080.

### [Pictionary](games/pictionary)

Draw-and-guess party game — online AI-generated clues or offline word bank,
chosen at setup.

```bash
cd games/pictionary
echo "ANTHROPIC_API_KEY=your-key-here" > .env
```

Then from the repo root: `make pictionary`. Or directly: `make run`.

Open http://localhost:9090.

### [Guess the Personality](games/guess-the-personality)

AI-powered guess-who, single screen — Claude secretly picks a real famous
personality (actor, athlete, etc.) and gives progressively easier clues.

```bash
cd games/guess-the-personality
echo "ANTHROPIC_API_KEY=your-key-here" > .env
```

Then from the repo root: `make guess-the-personality`. Or directly: `make run`.

Open http://localhost:8081.