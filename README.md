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
- [ ] Trivia
- [ ] AI Host


## Games

⬜ Guess the Word
✅ Charades
⬜ Truth or Dare
⬜ Heads Up
✅ Pictionary
✅ Mafia
⬜ Codenames
⬜ Would You Rather
⬜ Trivia
⬜ Two Truths and a Lie
⬜ Rapid Fire

## Quick Start

### [Mafia](games/mafia/README.md)

Real-time multiplayer, browser-based.

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
make run
```

Open http://localhost:8080.

### [Pictionary](games/pictionary)

Draw-and-guess party game — online AI-generated clues or offline word bank,
chosen at setup.

```bash
cd games/pictionary
echo "ANTHROPIC_API_KEY=your-key-here" > .env
make run
```

Open http://localhost:9090.