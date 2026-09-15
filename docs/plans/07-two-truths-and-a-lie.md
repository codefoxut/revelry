# Two Truths and a Lie

One-liner: the round's Storyteller privately writes three statements about
themselves (two true, one lie), everyone else votes on which is the lie,
then it's revealed — correct guessers score, and the Storyteller scores
based on how many people they fooled.

Ports: frontend 4100, backend 9000 (bumped from the otherwise-expected
4000/9000 pairing — 4000 collides with the hub's own default port, see
`docs/plans/README.md`). `game_type: "two_truths_and_a_lie"`.

## Why this is a good closer for the roadmap

It reuses two patterns already built earlier in this batch rather than
introducing a third: private author-only data entry (like Wavelength's
Psychic-only target) and shuffled-anonymous-until-reveal content (like
Fill in the Blank's submissions). If both of those are built first, this
game is mostly assembly, not new design — good last game to build.

## Game loop / phases

`LOBBY -> SUBMITTING -> VOTING -> REVEAL -> ... -> GAME_OVER`

- Storyteller role rotates every round through the player list (same
  rotation-index pattern as Wavelength's Psychic).
- `SUBMITTING`: only the Storyteller acts — privately submits exactly 3
  statements plus which index (0/1/2) is the lie. Server stores
  `lie_index` server-side only; it must never be sent to any client before
  reveal, including the Storyteller's own future reconnects mid-round
  (fine to re-send it to the Storyteller specifically, just never to
  anyone else). Everyone else sees a "waiting for the Storyteller to write
  their statements…" placeholder.
- Once submitted, auto-advance (or Storyteller manually confirms) to
  `VOTING`.
- `VOTING`: the three statements are broadcast (text only, shuffled order
  is unnecessary here since there's no author-per-item to hide — there's
  only one author, hidden as a role not as a per-item mapping — so send
  them in the original order, no shuffle needed, simpler than Fill in the
  Blank). Every player **except** the Storyteller casts one vote for which
  index they think is the lie. Storyteller cannot vote (they know the
  answer) — enforce server-side.
- `REVEAL`: reveal `lie_index`, list who voted correctly, award points:
  each correct voter gets a fixed amount (e.g. 100); Storyteller gets
  points inversely related to how many guessed correctly (e.g. `100 *
  (wrong_guessers / total_guessers)` — the fewer people they fooled... wait,
  invert: reward fooling more people, so `100 * (wrong_guessers /
  total_guessers)` rewards a higher fooled-fraction, which is correct as
  written — double check this formula when implementing and write the
  intended behavior as a code comment since it's easy to get backwards).
- Rotate Storyteller, next round; fixed number of rounds; `GAME_OVER`
  leaderboard.

## Backend

`app/games/two_truths_and_a_lie/`:
- `phases.py`: `Phase = Literal["lobby", "submitting", "voting", "reveal",
  "game_over"]`.
- `prompt_hints.py` (optional, light): a small list of icebreaker category
  hints (e.g. "travel", "childhood", "job") shown to the Storyteller purely
  as inspiration, not required content — this game's content is
  player-generated, unlike every other game in the roadmap, so there is no
  real curated bank needed. Skip this file entirely if it doesn't add
  value; don't force a content bank where the game doesn't need one.
- `commands.py`: `SubmitStatementsCommand{statements: list[str] (len 3),
  lie_index: int}` (Storyteller only), `CastVoteCommand{choice_index}`,
  `RevealCommand`, `NextRoundCommand`, `StartGameCommand`.
- `events.py`: `RoundStartedEvent{storyteller_id}` (broadcast, no
  statements yet), `StatementsSubmittedEvent{statements: list[str]}`
  (broadcast, no `lie_index`), `PlayerVotedEvent{player_id}` (count-only),
  `RevealedEvent{lie_index, correct_voters: list[str], scores_delta:
  dict[str, int]}`, `GameOverEvent{scores}`.
- `engine.py`: `MIN_PLAYERS = 3` (Storyteller + at least 2 guessers, same
  reasoning as Fill in the Blank — need enough guessers for "fooled
  fraction" scoring to be meaningful). Validate `CastVoteCommand` rejects
  the current Storyteller. Validate `SubmitStatementsCommand` requires
  exactly 3 non-empty statements and `lie_index in {0,1,2}`.
- `GameStateOut` additions: `phase`, `round_number`, `total_rounds`,
  `storyteller_id`, `statements: list[str] | None` (populated once
  submitted), `voted_count`, `lie_index: int | None` (populated only at
  reveal, and only in the payload sent to non-Storyteller clients before
  reveal should it be entirely absent — same discipline as Wavelength's
  target field), `correct_voters: list[str] | None`, `scores`.

## Frontend

`GameView.tsx`:
- Storyteller view during `submitting`: 3 text inputs + a "this one's the
  lie" selector among the 3, submit button.
- Everyone else during `submitting`: waiting placeholder with the
  Storyteller's name.
- `voting`: 3 statement cards, tappable (Storyteller's own view here is
  disabled/read-only — they already know the answer, shouldn't see a vote
  UI at all, show them a spectator "waiting for votes" state instead).
- `reveal`: highlight the true lie, checkmark/cross next to each voter's
  pick (or a simple "N correct guessers" summary if per-voter breakdown
  feels like too much), Storyteller's fooled-fraction score, leaderboard.
- Store: same private-field discipline as Wavelength — `lie_index` only
  ever populated in state once a `RevealedEvent` actually arrives.

## Testing

- Backend: Storyteller can't vote (enforced server-side), `lie_index`
  never appears in any serialized payload before reveal for non-Storyteller
  clients (this is the critical test, mirror Wavelength's equivalent),
  exactly-3/valid-index validation on submission, fooled-fraction scoring
  formula matches the documented intent (write the formula test with an
  explicit worked example, e.g. 1 correct out of 3 guessers -> Storyteller
  gets 100 * 2/3).
- Frontend: store test that statements render without any lie indicator
  until reveal.
- E2E: 4 players, rotate through 2 rounds so two different people are
  Storyteller, confirm the previous Storyteller can vote in the next round
  (role correctly rotates off them) and the new one cannot.

## Open questions / risks

- Double-check the fooled-fraction scoring formula direction during
  implementation — it's easy to accidentally reward the Storyteller for
  being *guessed correctly* instead of for fooling people; write the unit
  test with a worked example before writing the implementation, not after.
- `MIN_PLAYERS = 3` judgment call, same caveat as Fill in the Blank.
