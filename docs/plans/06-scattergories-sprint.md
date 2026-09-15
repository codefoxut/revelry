# Scattergories Sprint

One-liner: host shows a letter + a handful of categories, everyone
privately types as many answers starting with that letter as they can
before a countdown ends, then the group reviews for duplicates/invalid
answers — only unique valid answers score.

Ports: frontend 3900, backend 8900. `game_type: "scattergories_sprint"`.

## Why this needs a server-driven countdown

First game with a hard timed phase that must auto-transition for everyone
simultaneously (not player-paced like every prior game). Model this on
`disconnect_grace.py`'s existing asyncio delayed-task pattern — same
building block Rapid Fire uses for its arm delay — rather than inventing a
new timer mechanism. If Rapid Fire is built first (per roadmap order), reuse
whatever helper/abstraction it introduces for "schedule a phase transition
N seconds from now, cancel-safe on room teardown" instead of duplicating it.

## Game loop / phases

`LOBBY -> ROUND_OPEN (writing) -> REVIEW -> SCORED -> ... -> GAME_OVER`

- `ROUND_OPEN`: server picks a letter (weighted away from rare ones like Q,
  X, Z — or exclude them entirely, simplest) and 3 categories for the
  round, starts a fixed countdown (e.g. 90s) via the scheduled-task
  pattern. Each player privately types answers into up to 3 text fields
  (one per category) — nothing is broadcast during this phase, submissions
  are silent until timer end (only a "player has submitted" flag, like
  Fill in the Blank's count-only signal, if a player finishes early and
  hits submit before the timer).
- Timer expiry (or all-submitted, whichever first) auto-transitions to
  `REVIEW`, using whatever each player had typed at that moment (partial
  answers count, blanks count as no answer for that category).
- `REVIEW`: host cycles through each category one at a time
  (`NextCategoryCommand`); for the current category, all players' answers
  are shown together (grouped so identical text is visually clustered).
  Any player can flag an answer as invalid (doesn't start with the letter,
  isn't a real answer, etc.) via a lightweight peer vote — simplest rule:
  majority-flag invalidates it, don't overbuild a full voting UI for this.
- `SCORED`: tally per category — unique (no other player wrote the same
  normalized text) + not flagged invalid = 3 points; duplicate (≥2 players
  wrote the same normalized text) + not flagged invalid = 1 point each;
  blank or flagged invalid = 0. Normalize text for duplicate-detection by
  lowercase + trim (don't attempt fuzzy/spelling-tolerant matching — out of
  scope, exact-normalized match only).
- Fixed number of rounds (new letter + categories each time), then
  `GAME_OVER` leaderboard.

## Backend

`app/games/scattergories_sprint/`:
- `phases.py`: `Phase = Literal["lobby", "round_open", "review", "scored",
  "game_over"]`.
- `content.py`: `LETTERS` (list, excluding Q/X/Z), `CATEGORIES` (list of
  ~40 category name strings, e.g. "Things you find in a kitchen").
- `commands.py`: `SubmitAnswersCommand{answers: dict[str, str]}` (category
  -> text, can be called multiple times before timer end to update),
  `NextCategoryCommand` (host, review phase), `FlagInvalidCommand{author_id,
  category}` (peer vote), `NextRoundCommand`, `StartGameCommand`.
- `events.py`: `RoundStartedEvent{letter, categories, ends_at_ms}`
  (`ends_at_ms` is a server timestamp so clients can render a synced
  countdown without trusting their own clock start point),
  `PlayerSubmittedEvent{player_id}` (count-only, for early finishers),
  `TimerExpiredEvent{}`, `ReviewCategoryEvent{category, answers:
  list[{player_id, text}]}`, `AnswerFlaggedEvent{player_id, category,
  flag_count}`, `RoundScoredEvent{scores_delta, breakdown: list[{player_id,
  category, points}]}`, `GameOverEvent{scores}`.
- `engine.py`: `MIN_PLAYERS = 2`. `TOTAL_ROUNDS = 5`, `ROUND_SECONDS = 90`.
  Scheduled task for timer expiry must be cancelled cleanly if the game
  ends early / room closes (reuse Rapid Fire's helper if it exists by the
  time this is built).
- `GameStateOut` additions: `phase`, `round_number`, `total_rounds`,
  `letter`, `categories`, `ends_at_ms`, `submitted_count`,
  `review_category: str | None`, `review_answers: list[{player_id, text,
  flag_count}] | None`, `scores`.

## Frontend

`GameView.tsx`:
- `round_open`: three text inputs (one per category, labelled with the
  required letter prefixed, e.g. "B: ___"), a client-side countdown ring
  computed from `ends_at_ms - Date.now()` (resyncs automatically on
  reconnect since it's derived from a server timestamp, not a locally
  started interval), submit button (optional — auto-submits current text
  at timer end regardless).
- `review`: current category's answers listed, each with a "flag" button
  (toggle your own flag on/off), live flag count.
- `scored`: per-category point breakdown, round total, running
  leaderboard.
- Mobile testing note: three stacked text inputs + on-screen keyboard on a
  390px viewport is the layout most likely to need real adjustment — budget
  time for this in the mobile Playwright pass, don't assume the desktop
  layout just reflows fine.

## Testing

- Backend: normalization/duplicate-detection (case, whitespace), scoring
  math (unique vs duplicate vs blank vs flagged), timer expiry
  auto-transition (mock the clock/scheduled task, don't sleep 90s in
  tests), letter/category selection avoids repeats within a game if
  reasonable (nice-to-have, not required), partial-submission handling
  (player never called `SubmitAnswersCommand` at all for a round — must not
  crash scoring).
- Frontend: store test for countdown derivation from `ends_at_ms`,
  flag-toggle state.
- E2E: 3 players, one duplicate answer between two of them, one unique,
  one blank — confirm scoring breakdown matches expectations after review
  and flagging.

## Open questions / risks

- Flag-to-invalidate majority rule is a judgment call (recommend: flags
  from >50% of *other* players invalidates); revisit after playtesting.
- Fuzzy matching (typos, minor spelling variants counted as duplicates) is
  explicitly out of scope for v1 — exact normalized match only.
