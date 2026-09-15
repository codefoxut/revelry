# Fill in the Blank

One-liner: host shows a mad-libs-style prompt with a blank, everyone
submits a word/phrase anonymously, submissions are revealed shuffled, then
everyone votes for the funniest (not their own) — most votes wins the
round.

Ports: frontend 3700, backend 8700. `game_type: "fill_in_the_blank"`.

## Why this needs anonymity handling

First game (alongside Two Truths and a Lie) where the *authorship* of
content must be hidden through part of the round. Submissions must be
broadcast shuffled with author identity withheld until the vote closes —
get this ordering right or the game spoils itself. This is different from
Wavelength/Family Feud's "hide data from most players" — here everyone
eventually sees all the content, just not who wrote what, until reveal.

## Game loop / phases

`LOBBY -> PROMPT_OPEN (submitting) -> SUBMISSIONS_REVEALED -> VOTING ->
RESULTS -> ... -> GAME_OVER`

- `PROMPT_OPEN`: host shows the fill-in-the-blank sentence; every player
  (host included, host can play too) submits one line of text. Server
  tracks who has submitted (count only, not content) so host knows when to
  advance.
- Host manually advances (`RevealCommand`) — don't force-wait for 100%,
  same reasoning as Would You Rather (an AFK player shouldn't stall the
  room). Anyone who didn't submit in time is simply excluded from that
  round's submissions.
- `SUBMISSIONS_REVEALED`: server shuffles the submitted texts (fixed random
  seed per round, stored server-side as `submission_id -> {text,
  author_id}`, but the event sent to clients omits `author_id` and only
  includes `submission_id` + `text`) and broadcasts the shuffled list.
- `VOTING`: every player casts one vote for a `submission_id` — server
  must reject a player voting for their own submission (needs the
  author map to check this server-side even though it's not sent to
  clients).
- `RESULTS`: reveal the full map (submission -> author) plus vote tallies.
  Points: the submission with the most votes' author gets points (e.g. 100
  per vote received); ties split/each tied author scores.
- Fixed number of rounds, then `GAME_OVER` leaderboard.

## Backend

`app/games/fill_in_the_blank/`:
- `phases.py`: `Phase = Literal["lobby", "prompt_open",
  "submissions_revealed", "voting", "results", "game_over"]`.
- `prompts.py`: curated list of ~30 mad-libs-style sentence templates with
  a single blank (e.g. `"The worst thing to bring to a job interview is
  ___."`) — same curated-bank pattern as prior games.
- `commands.py`: `SubmitAnswerCommand{text}`, `RevealCommand`,
  `StartVoteCommand`, `CastVoteCommand{submission_id}`, `NextPromptCommand`,
  `StartGameCommand`.
- `events.py`: `PromptShownEvent{prompt, question_number, total_questions}`,
  `PlayerSubmittedEvent{player_id}` (count-only signal),
  `SubmissionsRevealedEvent{submissions: list[{submission_id, text}]}`
  (shuffled, no author), `PlayerVotedEvent{player_id}` (count-only),
  `VoteResultsEvent{results: list[{submission_id, text, author_id,
  votes}]}`, `RoundOverEvent{scores_delta}`, `GameOverEvent{scores}`.
- `engine.py`: `MIN_PLAYERS = 3` (need enough players that "vote for
  someone else's" is meaningful and anonymity isn't trivially broken by
  process of elimination with only 2 players). Server-side vote validation
  rejects self-votes by checking the hidden author map, returns an
  `ErrorEvent` to that client if attempted (shouldn't be possible from a
  correct client UI, but must be enforced server-side regardless — never
  trust the client to omit the option).
- `GameStateOut` additions: `phase`, `round_number`, `total_questions`,
  `prompt`, `submitted_count`, `submissions: list[{submission_id, text}] |
  None` (populated once revealed, still no author), `voted_count`,
  `results: list[{submission_id, text, author_id, votes}] | None`
  (populated once results phase), `scores`.

## Frontend

`GameView.tsx`:
- Symmetric view again (no Display/Controller split — host both plays and
  paces, like Would You Rather).
- `prompt_open`: text input + submit button, "n / total submitted" counter,
  locks after submitting (show "waiting for others…" with your own
  submitted text visible to you only, client-side, not from any event).
- `submissions_revealed` / `voting`: list of shuffled submission cards;
  each is tappable to vote except the one matching the text you personally
  submitted client-side-cached (extra client-side safety net on top of the
  required server-side check — belt and suspenders, but the server check is
  the one that actually matters).
- `results`: reveal author name under each card, vote count, highlight the
  round winner(s), running leaderboard.
- Store: cache your own submitted text locally (component/session state,
  not from a server event — server never echoes authorship back to you
  early) purely so the UI can grey out your own card during voting.

## Testing

- Backend: self-vote rejection (critical — write this test first), shuffle
  doesn't leak author via event payload (assert `author_id` absent from the
  `SubmissionsRevealedEvent` serialization, not just "correct in practice"),
  tie handling in results, non-submitters excluded cleanly (don't crash if
  0 or 1 person submitted a given round).
- Frontend: store test that submissions list never contains an `author_id`
  field until `results`.
- E2E: 3 players submit, one abstains (assert round still proceeds with
  2 submissions), vote, confirm nobody can select their own card in the
  browser UI, confirm results reveal authors correctly.

## Open questions / risks

- `MIN_PLAYERS = 3` is a judgment call for anonymity to feel meaningful —
  revisit if playtesting says otherwise.
- Decide tie-scoring exact split (recommend: every tied author gets full
  points, simplest and generous, matches party-game spirit over rigor).
