# Mafia — Future Upgrades

A working list of ideas for where this game can go next, past the initial 17-step build
and the mafia night-kill consensus/lock feature. Nothing here is committed or scheduled —
pick an item, discuss the approach, then implement it one step at a time (same process
used for every step so far: brief design discussion before code, verify end-to-end before
calling it done).

**Permanently out of scope:** in-game chat. The user has explicitly said "I dont want chat
option here" more than once — do not propose or build a chat feature unless that decision
is reversed.

## Current state (as of 2026-07-05)

- Roles: Villager, Mafia, Detective, Doctor (`backend/app/games/mafia/roles.py`).
- Phases: LOBBY → NIGHT → DAY → VOTING → ELIMINATION → (NIGHT | GAME_OVER), driven by a
  generic `StateMachine` (`backend/app/games/mafia/engine.py`).
- Night action: mafia teammates see each other's live picks and must explicitly lock a
  matching target; disagreement/partial-lock kills a random non-mafia player instead of no
  one. Doctor protect and detective investigate are unchanged (private, resolve
  immediately/at night resolution).
- Day: open (non-secret) plurality voting; ties are "no elimination."
- Reconnection: lobby-phase-only 30s grace period before a disconnected player is dropped;
  mid-game disconnects just wait for a fresh WS connection with the same `player_id`.
- Persistence: SQLite for durable data (users, matches, stats — models exist but are
  largely unused by the live game yet); everything about an *active* game (rooms, engine
  state) lives in a single process's memory behind an `InMemoryStore`/`KeyValueStore`
  interface (`backend/app/platform/stores/`) — no Redis, no multi-process support.
- No authentication — players are anonymous per-room UUIDs stored in the browser's
  `sessionStorage`.
- Single game type, single standalone deployment (`games/mafia/`) — not on a shared
  multi-game platform (that was explicitly decided against; see project memory).

---

## 1. New roles

The `Role` dataclass + `ROLE_REGISTRY` (`roles.py`) was deliberately built to make this
easy — a new role is a new `Role(...)` entry plus a branch in
`MafiaGameEngine._submit_night_action`/`_resolve_night`/`_check_win` if its behavior isn't
just "vote at night" or "no ability." Candidates, roughly in order of implementation
difficulty:

- **Vigilante** (town, acts at night): can shoot a player once per game. Needs a
  once-per-game-use flag per player, and a "vigilante killed a town member" penalty/
  self-destruct rule is a common classic-Mafia variant worth deciding on explicitly.
- **Mayor / town leader** (town, no night action): revealing this role publicly doubles
  their day vote weight. First role that needs a vote *weight* concept — today's
  `_plurality_target` just counts entries in `self._votes`, one per player.
- **Silencer/Framer** (mafia, acts at night): a second mafia-team night action alongside
  the kill target — e.g. prevents one town player from voting the next day, or frames a
  town player so the detective's investigation on them returns "mafia." Exercises the
  "more than one night-action type per role" case the engine doesn't have yet (mafia today
  only ever submits a kill target).
- **Jester** (independent/third team): wins alone if voted out by the town. First role
  that isn't Town or Mafia — `Team` enum and `_check_win` currently hard-code a two-team
  model (`mafia_alive == 0` / `mafia_alive >= town_alive`); a third team needs a real
  design pass on win conditions, not just a new enum value.
- **Witch/Bodyguard variants**: swap-target or redirect-the-kill abilities — interesting
  because they need to resolve in a specific order relative to the mafia's kill and the
  doctor's protect (currently: mafia targets → doctor protect cancels → done; a redirect
  role needs an explicit resolution-order contract, worth writing out before implementing
  more than one such role).
- **Role configuration per room**: today `_role_composition` is a fixed formula (1 mafia
  per 4 players, then detective, then doctor, rest villagers). A host-configurable role
  list (toggle which roles are in the deck, how many mafia) would need a new lobby-phase
  UI + a `RoomManager`-level setting persisted before `start_game`.

## 2. Night-phase & voting mechanics

- **Extend live-pick visibility to other multi-actor scenarios.** The mafia
  live-picks/lock pattern built this session (`MafiaTargetsUpdatedEvent` /
  `send_to_players`) generalizes to any "small team must coordinate" mechanic — e.g. if a
  future variant adds a second mafia-like faction (Triad, Cult), the same
  `send_to_players(room_code, team_ids, event)` primitive on `ConnectionManager` can be
  reused directly.
- **Day-vote parity with the night-lock idea**: right now day voting is open/plurality
  with a tie meaning no elimination — consider whether a tie should also have a
  higher-stakes fallback (random elimination among the tied players?) for consistency with
  the new night-kill philosophy, or whether "no elimination" is fine to keep for day votes
  specifically since the whole town (not just a 2-3 person mafia team) failed to agree.
  Worth an explicit product decision, not just copying the night behavior over.
- **Self-target / abstain rules**: audit whether every role can currently target
  themselves (e.g. doctor self-protect is used in tests) and whether that's intended for
  all night-acting roles, or should be blocked for some (e.g. can vigilante target self?).
- **Un-vote / change vote before locking in the day phase**: day votes currently apply
  immediately and broadcast per cast (`VoteCastEvent`); there's no "lock" concept on the
  day side the way there now is on the mafia night side. Could mirror the same
  submit-then-lock pattern for symmetry, or deliberately leave day voting as "votes are
  public and can change right up until Advance phase" (current behavior) since day voting
  is supposed to be transparent group discussion, not a secret ballot.

## 3. Timers & pacing

- **Phase timers**: today the host manually clicks "Advance phase." A per-phase countdown
  (e.g. 60s to submit a night action, 90s to discuss + vote) would need: a server-side
  timer per room (background `asyncio.Task`, similar shape to
  `DisconnectGraceManager`), a WS event broadcasting the deadline so all clients render the
  same countdown, and a decision about what happens if the timer expires without full
  mafia consensus (falls into the same random-kill fallback path already built) or without
  enough day votes.
- **Auto-advance for the host**: optionally let the host toggle "auto-advance when timer
  expires" vs. today's fully-manual model.
- **Warn players before locking**: a short "3...2...1" UI countdown once a mafia player
  hits Lock and is waiting on teammates, so it's clear the phase could advance any moment
  once the host acts.

## 4. Player experience / UI polish

- **Spectator mode improvements**: spectators already exist at the room-join level
  (`as_spectator` on `join_room`) but `GameView.tsx` has no spectator-specific view (they
  currently see nothing meaningful since they have no role/aliveness). A dedicated
  spectator layout showing public game state (phase, round, alive players, public votes)
  without any private-role leakage would make joining as a spectator actually useful.
  Notably this must NOT leak the mafia's `mafia_night_picks` broadcast to spectators — that
  event is intentionally scoped to living mafia sockets only.
  the reasoning above.
- **Sound/animation on eliminations and phase changes** — currently everything is silent
  text updates.
- **Host controls during a live game**: pause the game, force-skip a phase, or remove/kick
  a disconnected player mid-game (kicking today only works pre-game via the lobby's
  `kick_player`; the disconnect-grace mechanism is explicitly lobby-phase-only, see
  `disconnect_grace.py`'s "why" comment — resurfacing this for in-game kicks needs the
  engine's `_alive`/`_roles` dicts and the room roster to stay in sync, which was
  deliberately deferred rather than solved half-way).
- **Post-game summary screen**: role reveal for every player, a simple timeline of who
  died when and by what (night kill vs. vote), rather than just a "town/mafia wins" banner.
- **Mobile polish pass**: dedicated touch-target sizing check for the mafia lock button /
  target picker lists on small screens — not verified in an actual mobile browser yet
  (no browser tool available in this environment for the whole project so far).

## 5. Social & meta features

- **Accounts/auth**: `app/models/user.py` and friends already exist but aren't wired to
  anything live — today every player is an anonymous per-room UUID. Real accounts would
  enable persistent stats, friends lists, and reconnecting to a room from a different
  device/session.
- **Match history & stats**: `Match`/`MatchParticipant`/`PlayerStatistics` models exist
  unused. Recording a completed game (winning team, role each player had, who was
  eliminated when) would need a write path added to `_resolve_night`/`_resolve_elimination`/
  the `GAME_OVER` transition, or a listener on `GameOverEvent`.
- **Public room browser / quickplay matchmaking**: today the only way into a room is a
  direct invite link/code. A "find a public game" queue is a materially different feature
  (needs room visibility state beyond `is_private`, and a matching/waiting-room flow).
- **Achievements**: `app/models/achievement.py` exists unused — same story as match
  history, needs a real trigger point once match history is being recorded.

## 6. Scaling & infrastructure

This is the biggest structural gap if the game ever needs to run on more than one backend
process:

- **Everything server-side is single-process in-memory today** (`InMemoryStore`,
  `MafiaGameEngine` instances, `ConnectionManager`'s socket dict, `DisconnectGraceManager`'s
  scheduled tasks). This is fine for one uvicorn worker but breaks the moment you run more
  than one process/replica — a player's WebSocket could land on a different process than
  the one holding their room's engine state.
- If horizontal scaling is ever needed: introduce Redis (or similar) behind the existing
  `KeyValueStore` interface for room/game state (the interface was designed for exactly
  this swap — see `app/platform/stores/base.py`), plus a pub/sub layer so
  `ConnectionManager.broadcast`/`send_to_player`/`send_to_players` can fan out across
  processes, not just to sockets held by the same process. This is a substantial change,
  not a drop-in — flag it as its own dedicated project rather than a quick add-on.
- **Rate limiting / abuse protection**: no rate limiting exists on room creation, joining,
  or WS commands today. Before any public deployment, add per-IP or per-player throttling
  on `POST /api/rooms`, `POST /api/rooms/{code}/join`, and WS command frequency.
- **Observability**: no structured logging, metrics, or tracing yet — currently just
  whatever uvicorn prints. Worth adding before running this for real users at scale (game
  duration, disconnect frequency, room sizes, error rates).

## 7. Testing & CI

- **No CI pipeline exists** — step 17 explicitly replaced GitHub Actions with local
  Makefile targets per the user's instruction at the time. If the user wants CI later,
  that's new scope (confirm first — this was deliberately descoped, not left unfinished).
- **Load/soak testing**: no test exercises many concurrent rooms or high player counts per
  room (`max_players` exists in `RoomManager` but the real ceiling under load — WS fan-out
  cost, memory per active engine — hasn't been measured).
- **Property-based / fuzz testing** for the state machine and role interactions (e.g.
  Hypothesis) could catch edge cases the current example-based tests don't (weird player
  counts, mafia = majority from round 1, all-mafia-eliminated-simultaneously-with-parity
  edge cases).
- **Frontend component/interaction tests**: current frontend suite (`vitest`, node
  environment) only tests pure logic (`RoomSocket`, `roomStore`) — no rendered-component
  tests for `GameView.tsx`/`LobbyView.tsx` yet (would need jsdom + testing-library added).
- **Browser-based manual/E2E verification**: every UI-affecting step in this project
  (steps 13/14, the mafia lock UI) has been verified via `tsc --noEmit`/`eslint`/logic
  tests and live WS smoke scripts, but never in an actual browser (no browser tool
  available in this environment). Worth a real manual pass, or adding Playwright, before
  trusting the UI fully.

## 8. Security hardening

- **Server-side validation is already the source of truth for gameplay** (the engine
  rejects invalid actions regardless of what the client sends) — good foundation, keep it
  that way as new roles/mechanics are added rather than trusting client-side gating.
- **Private information leakage audit**: worth a periodic check that role assignments,
  detective results, and now `mafia_night_picks` are never broadcast room-wide by mistake
  — this class of bug (accidentally using `broadcast` instead of `send_to_player`/
  `send_to_players`) is the single easiest way to break the game's trust model, and there's
  no automated lint/test that structurally prevents it beyond the existing per-feature
  tests asserting non-recipients get silence.
- **Session/identity spoofing**: player identity today is just a UUID passed as a WS query
  param with no auth — anyone who learns another player's `player_id` (e.g. via a leaked
  URL or browser devtools) can connect as them. Not a real risk for a casual party game
  among friends, but worth a note if this ever gets exposed beyond trusted groups.

---

## How to use this list

When picking something up:
1. Re-read the relevant "Current state" bullet above and the actual code (this list may
   drift out of date — verify against `backend/app/games/mafia/` and `frontend/` before
   trusting a description here).
2. Discuss scope/approach briefly before implementing (matches how every prior step in
   this project has been done).
3. Update or prune this file once an item ships or is deliberately dropped, the same way
   the main README's game roadmap checklist is kept current.
