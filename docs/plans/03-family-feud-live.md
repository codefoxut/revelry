# Family Feud Live

One-liner: two teams, host reads a survey question with a hidden ranked
board of answers, first team to buzz gets control and guesses answers to
reveal board slots, three strikes passes control to the other team for one
steal attempt.

Ports: frontend 3600, backend 8600. `game_type: "family_feud"`.

## Why this is the highest-risk remaining game

It's the only game in the roadmap that needs **teams** instead of a flat
player roster — every other game (Mafia included) treats players as an
undifferentiated list (aside from role secrecy). This needs a genuine new
primitive: team assignment during lobby, team-scoped strikes, and
team-scoped final scoring. Build this game last among the "easy" ones, or
budget extra time — it touches `platform/room.py`'s player model more than
any other fork so far.

## Game loop / phases

`LOBBY -> TEAM_ASSIGN -> QUESTION_OPEN (buzz for control) -> ANSWERING ->
STEAL -> ROUND_OVER -> ... -> GAME_OVER`

- `TEAM_ASSIGN`: added to lobby, not a separate top-level phase necessarily
  — players pick "Team A" / "Team B" (or host assigns) before Start Game is
  enabled; require both teams non-empty and roughly balanced (don't hard
  block on exact balance, just require ≥1 per team).
- `QUESTION_OPEN`: host reveals the survey prompt (board answers still
  hidden, only point values' *count* is known — e.g. "8 answers"). Either
  team's players can buzz; first buzz gives that team "control".
- `ANSWERING`: the controlling team's players speak answers out loud (not
  typed — same verbal pattern as Trivia Showdown's judge step). Host either
  marks a board slot revealed (`RevealSlotCommand{slot_index}`, means they
  guessed correctly) or adds a strike (`StrikeCommand`, wrong guess). Any
  member of the controlling team can keep guessing after a correct reveal;
  3 strikes ends their team's turn.
- After 3 strikes: `STEAL` — the other team gets exactly one guess. Host
  either reveals one more slot (steal succeeds, that team takes all
  currently-revealed board points) or marks it wrong (steal fails,
  controlling team keeps the points).
- `ROUND_OVER`: sum of revealed slot points awarded to whichever team ends
  up owning the board; show round result.
- Fixed number of rounds, then `GAME_OVER` with team totals + winning team.

## Backend

`app/games/family_feud/`:
- `phases.py`: `Phase = Literal["lobby", "question_open", "answering",
  "steal", "round_over", "game_over"]`.
- `boards.py`: curated list of ~15 `{prompt: str, answers: [{text: str,
  points: int}, ...]}` (answers sorted descending by points, points per
  round should sum to a round number like 100 for satisfying scoring — same
  curated-content-bank pattern as Trivia Showdown's `questions.py`).
- **Team model**: extend `Player` (or add a parallel field in this game's
  own state, NOT in the shared `platform/room.py` `Player` model — keep the
  team concept scoped to this game's `GameState`, e.g. `team_of: dict[str,
  Literal["a","b"]]`, rather than polluting the shared room/player schema
  used by every other game). Confirm this scoping approach before writing
  code — it's the key design decision for this game.
- `commands.py`: `JoinTeamCommand{team: Literal["a","b"]}` (lobby only),
  `BuzzInCommand`, `RevealSlotCommand{slot_index}`, `StrikeCommand`,
  `StealRevealCommand{slot_index}` / `StealMissCommand`,
  `NextRoundCommand`, `StartGameCommand`.
- `events.py`: `TeamJoinedEvent{player_id, team}`,
  `QuestionShownEvent{prompt, answer_count}`,
  `PlayerBuzzedEvent{player_id, team}`,
  `SlotRevealedEvent{slot_index, text, points}`,
  `StrikeEvent{team, strikes}`, `StealPhaseEvent{team}`,
  `RoundOverEvent{team_awarded, points, board: full revealed list}`,
  `GameOverEvent{team_scores: dict[str, int], winning_team}`.
- `engine.py`: `MIN_PLAYERS = 2` per team is ideal but don't hard-require
  it — allow uneven teams; `MIN_PLAYERS = 2` overall (at least 2 total
  players across both teams, same floor as other games).
- `GameStateOut` additions: `phase`, `round_number`, `total_rounds`,
  `prompt`, `board: list[{text, points, revealed: bool}]` (text/points
  hidden — `null`/omitted — for unrevealed slots on the wire, same
  hidden-until-revealed pattern Codenames uses for the assassin/team
  assignments), `controlling_team`, `strikes: int`, `team_scores:
  dict[str, int]`.

## Frontend

`GameView.tsx`:
- Lobby gets a team-picker step before Start Game (extend
  `LobbyView.tsx`, not a separate route).
- Host (Display): shows the full board (all slots, even hidden ones show
  only their point value blanked out as "???"), prompt, buzz/strike/steal
  controls, team scores side-by-side.
- Contestant (Controller): shows same board (read-only) grouped by their
  own team's turn state — "Your team is answering!" / "Other team is
  answering" / "Steal chance!" banners, plus a buzz button only enabled
  during `question_open`.
- Board slot reveal should animate (flip-in), matching the genre's feel —
  reasonable polish target, not required for correctness.

## Testing

- Backend: team assignment validation (can't start without ≥1 per team,
  can switch teams pre-start), strike counting to exactly 3 triggers steal,
  steal success/failure scoring math, round-over point summation, game-over
  on last round with correct winning-team determination (including a tie
  case — decide tie behavior: no winner banner, "It's a tie" text like
  Trivia Showdown already has for individual ties).
- Frontend: store tests for board-slot reveal merging into state, team
  score display.
- E2E: 2v2 (or 1v2) — buzz, reveal two slots, strike three times, steal
  succeeds, confirm points landed on the stealing team; run to game over,
  confirm winning team shown on all 4 clients.

## Open questions / risks

- Confirm the team-scoping decision above (team data lives in this game's
  `GameState`, not the shared `Player` model) before implementation — this
  is the one architectural call worth a second look, since it's the only
  place "team" would otherwise leak into shared platform code used by 6
  other non-team games.
- Decide whether unbalanced teams should be allowed to start (recommend:
  yes, host's call, don't add a hard gate).
