# Rapid Fire

One-liner: pure reaction-speed buzzer — host arms a round, a random delay
later everyone gets the "GO" signal at the same instant, fastest correct
buzz wins the round.

Ports: frontend 3500, backend 8500. `game_type: "rapid_fire"`.

## Why this is the trickiest "simple" game

No trivia content, no judging — the entire game is a timing primitive. The
hard part is fairness: "GO" must be perceived as simultaneous by every
client despite network latency, and a buzz sent before "GO" must be
penalized (jumping the gun), not just ignored.

Approach: server is the single source of truth for time. The server picks
the random arm delay, waits, then broadcasts a `GoEvent` carrying its own
server timestamp. Each client's buzz command reciprocally includes nothing
client-side-timed (don't trust client clocks) — the server computes
reaction time as `server_receive_time(buzz) - server_send_time(go)`. A buzz
received while phase is still `armed` (before `GoEvent` was sent) is an
early buzz, not a fast one.

## Game loop / phases

`LOBBY -> ROUND_ARMED -> ROUND_LIVE -> ROUND_RESULT -> ... -> GAME_OVER`

- Host triggers `StartRoundCommand`. Server picks a random delay (e.g.
  2–6s), transitions to `ROUND_ARMED` immediately (so UI shows "get
  ready…"), schedules an asyncio task (same pattern as
  `disconnect_grace.py`) to fire at the delay.
- Delay fires -> phase becomes `ROUND_LIVE`, broadcast `GoEvent`.
- Any `BuzzInCommand` while `ROUND_ARMED`: record as early-buzz, that
  player is disqualified for this round (locked out, shown a "too early!"
  state), does NOT end the round for others.
- Any `BuzzInCommand` while `ROUND_LIVE` from a non-disqualified,
  not-yet-buzzed player: first one wins the round, transition to
  `ROUND_RESULT`, all others' buzz attempts after that are ignored (came in
  after the winner).
- If nobody buzzes within e.g. 5s of `GoEvent`, auto-transition to
  `ROUND_RESULT` with no winner for that round (nobody scores).
- `ROUND_RESULT`: show winner + their reaction time in ms, plus every other
  player's time (or "disqualified" / "no buzz").
- Fixed number of rounds (e.g. 8), then `GAME_OVER` with total points
  leaderboard (1 point per round win; ties/no-winner rounds score nobody).

## Backend

`app/games/rapid_fire/`:
- `phases.py`: `Phase = Literal["lobby", "round_armed", "round_live",
  "round_result", "game_over"]`.
- No content bank file needed. Optional: a small `prompts.py` list of
  flavor category words shown during `round_armed` purely for atmosphere
  (not functional) — nice-to-have, skip if it adds no value.
- `commands.py`: `StartRoundCommand`, `BuzzInCommand`, `NextRoundCommand`.
- `events.py`: `RoundArmedEvent{round_number, total_rounds}`,
  `GoEvent{server_time_ms}`, `PlayerBuzzedEarlyEvent{player_id}`,
  `RoundWonEvent{player_id, reaction_ms}`, `RoundTimedOutEvent{}`,
  `GameOverEvent{scores}`.
- `engine.py`: `MIN_PLAYERS = 2`. `TOTAL_ROUNDS = 8`. Needs a live asyncio
  timer handle per room (arm delay + no-buzz timeout) — model directly on
  `disconnect_grace.py`'s scheduling/cancellation pattern so a room
  teardown or early buzz-in cleanly cancels the pending task.
- `GameStateOut` additions: `phase`, `round_number`, `total_rounds`,
  `disqualified: list[str]` (early buzzers this round), `winner_id:
  str | None` (this round's), `reaction_times: dict[str, int] | None`,
  `scores: dict[str, int]`.

## Frontend

`GameView.tsx`:
- Host (Display): shows round number, a large state indicator
  ("Get ready…" during armed, "GO!" flashed during live), "Start round" /
  "Next round" buttons, leaderboard.
- Contestant (Controller): a single big buzzer button. During `round_armed`
  it's visually neutral/waiting; the instant `GoEvent` arrives client-side
  it flashes green and becomes tappable — tapping before that must be
  possible (button isn't disabled during armed, so an eager tap registers
  as the early-buzz command) so the "jumped the gun" penalty can actually
  trigger.
- `round_result`: show this player's own reaction time prominently, plus
  the round winner's name/time.
- Store: cache `RoundWonEvent`/`PlayerBuzzedEarlyEvent` transiently for the
  flash message, same pattern as Trivia Showdown's `lastJudged`.

## Testing

- Backend: this is the one game where timing-dependent unit tests need
  care — use a fake/injectable clock or monkeypatch `asyncio`'s
  `call_later` in tests rather than real sleeps, so tests aren't flaky/slow.
  Cover: early buzz during armed is rejected as a win and marks
  disqualified; first live buzz wins; second live buzz after a winner is a
  no-op; no-buzz timeout transitions correctly; disconnect during armed
  cancels the scheduled task (no crash).
- Frontend: store test for early-buzz vs win event handling.
- E2E: script one contestant buzzing early (assert disqualified state, game
  continues), then a normal live buzz on the same round from another
  contestant (assert they can still win despite the other's disqualification).

## Open questions / risks

- Network jitter means true simultaneity is best-effort, not exact — this
  is expected and fine for a party game (same limitation every buzzer app
  has), don't over-engineer clock sync.
- Decide `TOTAL_ROUNDS` and arm-delay bounds as simple constants; not worth
  making configurable for v1.
