# Would You Rather Live

One-liner: host reads a "would you rather A or B" prompt, everyone votes
anonymously from their phone, host reveals the split.

Ports: frontend 3400, backend 8400. `game_type: "would_you_rather"`.

## Why this is simple

No judging, no correct answer, no asymmetric visibility — every event can
be a plain broadcast, same as Trivia Showdown minus the judge step. Good
first game to build after Trivia Showdown since it reuses that structure
almost directly, just swapping "buzz + judge" for "vote + reveal".

## Game loop / phases

`LOBBY -> QUESTION_OPEN (voting) -> REVEALED (split shown) -> ... -> GAME_OVER`

- `QUESTION_OPEN`: every player (host included — host plays too, they just
  also control pacing) can submit one vote, `a` or `b`. Vote is hidden from
  other players until reveal. Changing your vote before reveal is allowed
  (just overwrite).
- Host can reveal once all players have voted, or early (host judgment call
  — don't force a wait-for-everyone gate, someone may be AFK).
- `REVEALED`: show count/percentage for A and B, and which side each player
  landed on (this is a "social" game — the fun is seeing who agreed with
  who, not hiding it after reveal).
- No per-round winner, no points. `GAME_OVER` is just "last question was
  revealed" — recap screen shows every round's prompt + split, no
  leaderboard/winner.

## Backend

`app/games/would_you_rather/`:
- `phases.py`: `Phase = Literal["lobby", "question_open", "revealed", "game_over"]`
- `prompts.py`: curated list of ~40 `{option_a: str, option_b: str}` pairs,
  shuffled per room at game start (mirror `questions.py`'s structure/loader
  from Trivia Showdown).
- `commands.py`: `SubmitVoteCommand{choice: Literal["a","b"]}`,
  `RevealCommand`, `NextQuestionCommand`, `StartGameCommand`.
- `events.py`: `QuestionShownEvent{question_number, total_questions,
  option_a, option_b}`, `PlayerVotedEvent{player_id}` (no choice — just
  updates a "n/total voted" counter), `VotesRevealedEvent{votes: dict[str,
  Literal["a","b"]]}` (full map, since this game reveals everyone's pick —
  no anonymity requirement here, unlike Fill in the Blank/Two Truths),
  `GameOverEvent{}`.
- `engine.py`: `MIN_PLAYERS = 2`. Track `votes: dict[player_id, "a"|"b"]`
  per round in game state, cleared each `NextQuestionCommand`. Reveal just
  copies `votes` into the event/state.
- `GameStateOut` additions (in `app/schemas/room.py`): `phase`,
  `round_number`, `total_questions`, `option_a`, `option_b`, `voted:
  list[str]` (who has voted, not what — for the live counter),
  `revealed_votes: dict[str, str] | None` (only populated once revealed).

## Frontend

`GameView.tsx`:
- Everyone (host and contestants) sees the same core view — no
  Display/Controller split needed here since there's no judging role. Host
  additionally sees the Reveal/Next buttons.
- `question_open`: two big tappable option cards (A / B), highlight
  whichever the player picked; "n / total voted" counter.
- `revealed`: horizontal split bar (% A vs % B) + avatar row under each
  side showing who picked what.
- `game_over`: scrollable recap list of every prompt + its split (no
  winner banner — this game doesn't score).
- Store: no `lastJudged`/`gameOver`-with-winner pattern needed; can drop
  those fields from the Trivia Showdown store template entirely since there
  is no winner concept.

## Testing

- Backend: engine unit tests for vote submission/overwrite, reveal
  snapshotting votes, next-question clearing state, game-over on last
  question.
- Frontend: store tests for vote-counter updates and revealed-votes
  caching; vitest for the two-card / split-bar rendering logic if
  meaningfully complex.
- E2E: host + 2 contestants, vote split 2-1, reveal, confirm split shown
  correctly on all 3 clients, cycle to game over, confirm recap list length
  matches total prompts used.

## Open questions / risks

- None significant — lowest-risk game in the remaining 7. Mainly a content
  writing task (the 40 prompt pairs) plus the UI polish on the split-bar
  reveal.
