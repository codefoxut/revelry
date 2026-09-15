# Wavelength

One-liner: a hidden target sits somewhere on a spectrum between two
opposite concepts (e.g. "Hot ↔ Cold"); the round's Psychic sees the target
and gives a one-word clue out loud; everyone else drags a slider to guess
its position; points scale with how close the average guess lands.

Ports: frontend 3800, backend 8800. `game_type: "wavelength"`.

## Why this needs targeted (non-broadcast) send

This is the first game since Codenames to require truly private per-player
state: the target position must reach the Psychic's client only. Reuse
Codenames' existing mechanism for spymaster-only board data in
`dispatcher.py`/`connection_manager.py` (a targeted send to one player's
socket instead of the room-wide broadcast) rather than building a new
one — check how Codenames' engine marks an event as
recipient-scoped before writing this game's `RoundStartedEvent`.

## Game loop / phases

`LOBBY -> CLUE_GIVING -> GUESSING -> REVEAL -> ... -> GAME_OVER`

- Psychic role rotates every round through the player list (deterministic
  order, same rotation style as any turn-based engine — track
  `psychic_index` in game state, increment mod player count each round).
- `CLUE_GIVING`: Psychic alone receives the spectrum labels + exact target
  position (0–100). Everyone else receives only the spectrum labels (left
  concept, right concept), not the position. Psychic gives a one-word/short
  clue **out loud** (verbal, like Trivia Showdown's answer) — optionally
  types it in too so it displays for everyone (nice touch, not required);
  host has no special role here beyond being a normal player who might also
  rotate into Psychic.
- Psychic (or anyone, but Psychic is the natural pacer) advances to
  `GUESSING` once they've said the clue.
- `GUESSING`: every non-Psychic player drags a slider (0–100 float) and
  locks in a guess. Psychic cannot guess (they know the answer). Track
  submitted guesses; advance to reveal once all non-Psychic players have
  guessed or Psychic/host forces it.
- `REVEAL`: show the target position, every guess plotted on the same
  spectrum, and points. Scoring (classic Wavelength bands, adapted to a
  single averaged/closest-guess metric since this isn't team-vs-team):
  score each guesser individually based on distance from target — e.g.
  within 2 = 4pts, within 6 = 3pts, within 12 = 2pts, within 20 = 1pt, else
  0. Psychic scores the average of their guessers' points that round (or
  simpler: Psychic gets points equal to the closest single guesser's
  score) — pick one rule and keep it simple, document it in the README.
- Rotate Psychic, next round; fixed number of rounds; `GAME_OVER`
  leaderboard.

## Backend

`app/games/wavelength/`:
- `phases.py`: `Phase = Literal["lobby", "clue_giving", "guessing",
  "reveal", "game_over"]`.
- `spectrums.py`: curated list of ~50 `{left: str, right: str}` concept
  pairs (e.g. `{"left": "Overrated", "right": "Underrated"}`).
- `commands.py`: `GiveClueCommand{clue_text}` (optional text, Psychic only,
  advances phase), `SubmitGuessCommand{position: float}`,
  `RevealCommand`, `NextRoundCommand`, `StartGameCommand`.
- `events.py`: `RoundStartedEvent` — **two variants dispatched
  differently**: a public one broadcast to all
  (`{psychic_id, left_label, right_label}`, no position) and a private one
  sent only to the Psychic's socket (`{target_position}`). Also
  `ClueGivenEvent{clue_text}`, `PlayerGuessedEvent{player_id}`
  (count-only), `RevealedEvent{target_position, guesses: dict[str, float],
  points_awarded: dict[str, int]}`, `GameOverEvent{scores}`.
- `engine.py`: `MIN_PLAYERS = 3` (need at least 1 Psychic + 2 guessers for
  "average distance" scoring to mean anything). Rotation index stored in
  game state; server validates `SubmitGuessCommand` is rejected from the
  current Psychic (they must not be able to guess their own round).
- `GameStateOut` additions: `phase`, `round_number`, `total_rounds`,
  `psychic_id`, `left_label`, `right_label`, `target_position: float |
  None` (must be `None`/omitted for every player except when serialized
  for the Psychic specifically — this is the one field in the whole
  roadmap that requires per-recipient response shaping, confirm
  `dispatcher.py` supports per-socket state payloads, not just per-socket
  events, before assuming this is a drop-in), `guessed_count`,
  `guesses: dict[str, float] | None` (populated at reveal), `scores`.

## Frontend

`GameView.tsx`:
- Non-Psychic view: spectrum bar with the two labels at each end, a
  draggable slider (touch-friendly — this is the one UI element across all
  7 games that most needs real mobile-drag testing, don't skip the mobile
  Playwright pass), lock-in button.
- Psychic view: same spectrum bar but with the actual target marked (a
  thin indicator only they can see), clue text input, "Start guessing"
  button once ready.
- `reveal`: spectrum bar showing target + every guesser's marker + points
  earned per player, leaderboard.
- Store: `psychicSecret` field for the target position, populated only when
  a private event actually arrives (most clients simply never receive it,
  which is correct — don't fake/default it to a visible value for
  non-Psychics).

## Testing

- Backend: **the single most important test in this whole file** — assert
  the target position never appears in the serialized event/state payload
  sent to a non-Psychic connection. Also: Psychic can't submit a guess,
  rotation advances correctly and wraps around, scoring bands compute
  correctly at boundary distances.
- Frontend: store test that a client without the private event never has a
  target position populated.
- E2E: assert (by inspecting the actual WS frames received in each
  browser context, not just the rendered DOM) that only the Psychic's
  client ever receives the target value.

## Open questions / risks

- Confirm the dispatcher can actually target a single connection with a
  distinct state payload (not just a distinct event) before committing to
  this design — if it can't today, that's a small platform-layer addition
  needed before this game, not a per-game hack.
- Scoring rule (Psychic's own points derived from guessers') is a judgment
  call — pick the simplest version and note it's adjustable later.
