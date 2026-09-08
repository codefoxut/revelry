# 🎵 Name That Tune

Listen to a short melody and shout out the title before your team runs out
of guesses — single screen, teams take turns. No audio files, no
microphone: every clip is synthesized live in the browser.

## How to play

1. Enter 2+ team names and pick a category.
2. The active team's turn starts. Tap **Reveal Tune**, then tap the ▶
   button to play the melody. Replay it as many times as you like.
3. Shout out guesses. Tap **Got it!** to score a point, or **Pass** to hand
   the same tune to the next team as a steal chance.
4. Play continues turn by turn — tap **End Game** any time to see the final
   scoreboard.

## Why there are no audio files

This game is intentionally **offline-only**, with no AI-generated or
streamed audio option. Every tune is a public-domain melody (classical
themes, nursery rhymes, folk songs, anthems) that we hand-transcribed
ourselves into a plain note sequence — pairs of `[note_name, duration]`
like `["G4", 0.2]`. No audio recording of any performance is stored or
shipped, which sidesteps the licensing ambiguity around "royalty-free"
audio (recordings of PD compositions can still carry their own recording
copyright). Playback is synthesized entirely client-side with the
[Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)
(`OscillatorNode`), converting each note name to a frequency with the
standard equal-temperament formula. No API key, `.env`, or network access
is needed to play.

## Setup

From the repo root: `make name-that-tune`. Or directly:

```bash
cd games/name-that-tune
make install
make run
```

Open http://localhost:8084.

## Tune bank

Melodies live in `data/tunes.db`, seeded from `tools/seed_tunes.py`
(safe to re-run) across four categories: Classical, Nursery Rhymes,
Holiday, and Folk & Anthems.

```bash
make seed   # (re)populate data/tunes.db from the curated melody list
```

## Commands

| Command      | What it does                                  |
|---------------|------------------------------------------------|
| `make install` | Create `.venv` and install dependencies        |
| `make run`     | Start the server with auto-reload (port 8084)  |
| `make seed`    | (Re)populate the offline tune bank              |
| `make test`    | Run the pytest suite                            |
| `make clean`   | Remove `.venv` and caches                        |
