import random

from app.game_engine.base import Command, Event, GameEngine
from app.games.mafia.commands import (
    AdvancePhaseCommand,
    CastVoteCommand,
    LockNightActionCommand,
    RevealMayorCommand,
    StartGameCommand,
    SubmitNightActionCommand,
    WithdrawBombCommand,
)
from app.games.mafia.conflict_resolution import ConflictResolution
from app.games.mafia.day_tie_resolution import DayTieResolution
from app.games.mafia.events import (
    EliminationResultEvent,
    GameOverEvent,
    InvestigationResultEvent,
    MafiaPick,
    MafiaTargetsUpdatedEvent,
    MayorRevealedEvent,
    NightResultEvent,
    PhaseChangedEvent,
    PlayerRoleReveal,
    RoleAssignedEvent,
    TerroristBombStatusEvent,
)
from app.games.mafia.phases import MAFIA_TRANSITIONS, MafiaPhase
from app.games.mafia.role_assignment import assign_roles
from app.games.mafia.roles import NightActionKind, Role, Team
from app.platform.exceptions import InvalidGameStateError
from app.platform.state_machine import StateMachine


class MafiaGameEngine(GameEngine):
    """Drives Mafia's full phase sequence via the generic StateMachine. One
    instance lives per active game (constructed directly by
    GameSessionManager), so it holds its own in-memory state rather than
    round-tripping through a store on every command.
    """

    def __init__(self, room_code: str, rng: random.Random | None = None) -> None:
        self.room_code = room_code
        self._machine = StateMachine(MafiaPhase.LOBBY, MAFIA_TRANSITIONS)
        self._round_number = 0
        self._rng = rng if rng is not None else random.Random()
        self._roles: dict[str, Role] = {}
        self._alive: dict[str, bool] = {}
        # actor player_id -> target player_id, for every role's current
        # night pick (mafia/doctor/bodyguard/vigilante/escort/serial killer
        # all share this one dict; detective resolves immediately and never
        # occupies a slot in it).
        self._night_actions: dict[str, str] = {}
        self._mafia_locked: set[str] = set()
        # Terrorist's bomb spans a round boundary, so it lives here instead
        # of `_night_actions` — that dict is cleared every night, but a
        # planted bomb must survive into the following night's resolution.
        self._pending_bomb_target: str | None = None
        self._bomb_withdraw_requested: bool = False
        self._vigilante_uses_remaining: dict[str, int] = {}
        self._votes: dict[str, str] = {}
        self._conflict_resolution = ConflictResolution.KILL_ANY
        self._day_tie_resolution = DayTieResolution.NO_ELIMINATION
        self._mayor_revealed = False
        self._last_election_result: str | None = None

    @property
    def phase(self) -> MafiaPhase:
        return self._machine.phase

    @property
    def round_number(self) -> int:
        return self._round_number

    def role_for(self, player_id: str) -> Role | None:
        return self._roles.get(player_id)

    def is_alive(self, player_id: str) -> bool:
        return self._alive.get(player_id, False)

    async def handle_command(self, command: Command) -> list[Event]:
        if isinstance(command, StartGameCommand):
            return self._start_game(
                command.active_player_ids,
                command.conflict_resolution,
                command.day_tie_resolution,
                command.mafia_count,
                command.enabled_role_keys,
            )
        if isinstance(command, AdvancePhaseCommand):
            return self._advance_phase()
        if isinstance(command, SubmitNightActionCommand):
            return self._submit_night_action(command.player_id, command.target_player_id)
        if isinstance(command, CastVoteCommand):
            return self._cast_vote(command.player_id, command.target_player_id)
        if isinstance(command, LockNightActionCommand):
            return self._lock_night_action(command.player_id)
        if isinstance(command, RevealMayorCommand):
            return self._reveal_mayor(command.player_id)
        if isinstance(command, WithdrawBombCommand):
            return self._withdraw_bomb(command.player_id)
        raise ValueError(f"Unsupported command: {type(command).__name__}")

    def _start_game(
        self,
        active_player_ids: list[str],
        conflict_resolution: ConflictResolution,
        day_tie_resolution: DayTieResolution,
        mafia_count: int | None,
        enabled_role_keys: frozenset[str] | None,
    ) -> list[Event]:
        # Resolved (and can raise InvalidGameSettingsError) before any state
        # mutation, so a bad configuration never leaves the engine
        # half-transitioned.
        self._roles = assign_roles(
            active_player_ids, self._rng, mafia_count=mafia_count, enabled_role_keys=enabled_role_keys
        )

        self._machine.transition_to(MafiaPhase.NIGHT)
        self._round_number = 1
        self._alive = {player_id: True for player_id in active_player_ids}
        self._conflict_resolution = conflict_resolution
        self._day_tie_resolution = day_tie_resolution
        self._vigilante_uses_remaining = {
            player_id: role.max_uses
            for player_id, role in self._roles.items()
            if role.night_action_kind is NightActionKind.VIGILANTE_KILL and role.max_uses is not None
        }

        events: list[Event] = [PhaseChangedEvent(phase=self.phase, round_number=self._round_number)]
        events.extend(
            RoleAssignedEvent(
                player_id=player_id,
                role_key=role.key,
                role_display_name=role.display_name,
                team=role.team.value,
                description=role.description,
                acts_at_night=role.acts_at_night,
                allow_self_target=role.allow_self_target,
            )
            for player_id, role in self._roles.items()
        )
        return events

    def _submit_night_action(self, player_id: str, target_player_id: str) -> list[Event]:
        if self.phase is not MafiaPhase.NIGHT:
            raise InvalidGameStateError("Night actions can only be submitted during the night")
        if not self.is_alive(player_id):
            raise InvalidGameStateError("Dead players cannot act")
        if not self.is_alive(target_player_id):
            raise InvalidGameStateError("Target must be alive")

        role = self._roles.get(player_id)
        if role is None or not role.acts_at_night:
            raise InvalidGameStateError("This role has no night action")
        if not role.allow_self_target and target_player_id == player_id:
            raise InvalidGameStateError(f"{role.display_name} cannot target themselves")

        kind = role.night_action_kind
        if kind is NightActionKind.MAFIA_KILL:
            self._night_actions[player_id] = target_player_id
            # Locking now requires unanimous agreement, so any mafia
            # changing their pick invalidates the whole team's locks, not
            # just their own — a teammate's existing lock was only
            # meaningful while the old agreement held.
            self._mafia_locked.clear()
            return [MafiaTargetsUpdatedEvent(picks=self._mafia_picks_snapshot())]
        if kind is NightActionKind.DETECTIVE_INVESTIGATE:
            target_role = self._roles[target_player_id]
            reported_team = target_role.investigate_as or target_role.team
            return [
                InvestigationResultEvent(
                    player_id=player_id, target_player_id=target_player_id, team=reported_team.value
                )
            ]
        if kind is NightActionKind.ORACLE_INVESTIGATE:
            target_role = self._roles[target_player_id]
            effective_team = target_role.investigate_as or target_role.team
            reported_team = Team.MAFIA if effective_team is Team.MAFIA else Team.TOWN
            return [
                InvestigationResultEvent(
                    player_id=player_id, target_player_id=target_player_id, team=reported_team.value
                )
            ]
        if kind is NightActionKind.VIGILANTE_KILL:
            if self._vigilante_uses_remaining.get(player_id, 0) <= 0:
                raise InvalidGameStateError("No vigilante shots remaining")
            self._night_actions[player_id] = target_player_id
            return []
        if kind is NightActionKind.TERRORIST_BOMB:
            if self._pending_bomb_target is not None:
                raise InvalidGameStateError("A bomb is already planted and pending detonation")
            self._night_actions[player_id] = target_player_id
            return []
        if kind in (
            NightActionKind.DOCTOR_PROTECT,
            NightActionKind.BODYGUARD_PROTECT,
            NightActionKind.ESCORT_BLOCK,
            NightActionKind.SERIAL_KILLER_KILL,
        ):
            self._night_actions[player_id] = target_player_id
            return []
        raise InvalidGameStateError(f"Role {role.key!r} has no night action handling")

    def _withdraw_bomb(self, player_id: str) -> list[Event]:
        if self.phase is not MafiaPhase.NIGHT:
            raise InvalidGameStateError("A bomb can only be withdrawn during the night")
        if not self.is_alive(player_id):
            raise InvalidGameStateError("Dead players cannot act")

        role = self._roles.get(player_id)
        if role is None or role.night_action_kind is not NightActionKind.TERRORIST_BOMB:
            raise InvalidGameStateError("Only the terrorist can withdraw a bomb")
        if self._pending_bomb_target is None:
            raise InvalidGameStateError("No bomb is currently planted")

        self._bomb_withdraw_requested = True
        return []

    def _lock_night_action(self, player_id: str) -> list[Event]:
        if self.phase is not MafiaPhase.NIGHT:
            raise InvalidGameStateError("Night actions can only be locked during the night")
        if not self.is_alive(player_id):
            raise InvalidGameStateError("Dead players cannot act")

        role = self._roles.get(player_id)
        if role is None or role.night_action_kind is not NightActionKind.MAFIA_KILL:
            raise InvalidGameStateError("Only mafia can lock a night-action target")
        if player_id not in self._night_actions:
            raise InvalidGameStateError("Choose a target before locking it in")

        mafia_ids = [
            pid for pid, r in self._roles.items() if r.night_action_kind is NightActionKind.MAFIA_KILL and self.is_alive(pid)
        ]
        current_targets = {self._night_actions.get(pid) for pid in mafia_ids}
        if len(current_targets) != 1 or None in current_targets:
            raise InvalidGameStateError("All mafia must choose the same target before locking in")

        self._mafia_locked.add(player_id)
        return [MafiaTargetsUpdatedEvent(picks=self._mafia_picks_snapshot())]

    def _mafia_picks_snapshot(self) -> list[MafiaPick]:
        mafia_ids = [
            pid
            for pid, role in self._roles.items()
            if role.night_action_kind is NightActionKind.MAFIA_KILL and self.is_alive(pid)
        ]
        return [
            MafiaPick(
                player_id=pid,
                target_player_id=self._night_actions.get(pid),
                locked=pid in self._mafia_locked,
            )
            for pid in mafia_ids
        ]

    def _reveal_mayor(self, player_id: str) -> list[Event]:
        if self.phase not in (MafiaPhase.DAY, MafiaPhase.VOTING):
            raise InvalidGameStateError("The mayor can only reveal during the day or voting")
        if not self.is_alive(player_id):
            raise InvalidGameStateError("Dead players cannot act")
        role = self._roles.get(player_id)
        if role is None or role.key != "mayor":
            raise InvalidGameStateError("Only the mayor can reveal")

        if self._mayor_revealed:
            return []
        self._mayor_revealed = True
        return [MayorRevealedEvent(player_id=player_id)]

    def _cast_vote(self, player_id: str, target_player_id: str) -> list[Event]:
        if self.phase is not MafiaPhase.VOTING:
            raise InvalidGameStateError("Votes can only be cast during voting")
        if not self.is_alive(player_id):
            raise InvalidGameStateError("Dead players cannot vote")
        if not self.is_alive(target_player_id):
            raise InvalidGameStateError("Target must be alive")

        self._votes[player_id] = target_player_id
        return []

    def _advance_phase(self) -> list[Event]:
        current = self.phase
        if current is MafiaPhase.LOBBY:
            raise InvalidGameStateError("Game hasn't started yet")
        if current is MafiaPhase.GAME_OVER:
            raise InvalidGameStateError("Game is already over")

        if current is MafiaPhase.NIGHT:
            return self._resolve_night()
        if current is MafiaPhase.VOTING:
            return self._resolve_voting()
        if current is MafiaPhase.ELIMINATION:
            return self._resolve_elimination()

        # DAY -> VOTING: no resolution needed.
        self._machine.transition_to(MafiaPhase.VOTING)
        return [PhaseChangedEvent(phase=self.phase, round_number=self._round_number)]

    def _resolve_night(self) -> list[Event]:
        # 1. Escort's block: remove the blocked player's pending action (and
        #    any mafia lock they held) before anything else resolves.
        escort_id = self._actor_id_for_kind(NightActionKind.ESCORT_BLOCK)
        blocked_id = self._night_actions.get(escort_id) if escort_id is not None else None
        if blocked_id is not None:
            self._night_actions.pop(blocked_id, None)
            self._mafia_locked.discard(blocked_id)

        # 2. Terrorist's bomb, resolved before anything else consumes
        #    `_night_actions`. A block cancels a pending withdrawal request
        #    (the bomb keeps ticking); otherwise a bomb armed from a
        #    previous night detonates now, joining the doctor-protectable
        #    pool below. Either way it's consumed — a fresh plant can only
        #    be armed once this round's bomb has resolved (step 8).
        terrorist_id = next(
            (pid for pid, role in self._roles.items() if role.night_action_kind is NightActionKind.TERRORIST_BOMB),
            None,
        )
        if terrorist_id is not None and blocked_id == terrorist_id:
            self._bomb_withdraw_requested = False

        bomb_kill: str | None = None
        if self._pending_bomb_target is not None:
            if self._bomb_withdraw_requested:
                self._pending_bomb_target = None
            else:
                bomb_kill = self._pending_bomb_target
                self._pending_bomb_target = None

        # 3. Mafia's consensus/fallback kill target.
        mafia_kill = self._resolve_mafia_kill()

        # 4. Bodyguard redirect against mafia's kill only: if their guarded
        #    target is mafia's victim, the bodyguard dies instead.
        bodyguard_id = self._actor_id_for_kind(NightActionKind.BODYGUARD_PROTECT)
        bodyguard_target = self._night_actions.get(bodyguard_id) if bodyguard_id is not None else None
        if (
            mafia_kill is not None
            and bodyguard_target is not None
            and mafia_kill == bodyguard_target
            and bodyguard_id is not None
            and self.is_alive(bodyguard_id)
        ):
            mafia_kill = bodyguard_id

        # 5. Serial Killer's independent kill, immune to the bodyguard
        #    redirect above (that's scoped to mafia's kill only).
        sk_id = self._actor_id_for_kind(NightActionKind.SERIAL_KILLER_KILL)
        sk_kill = self._night_actions.get(sk_id) if sk_id is not None else None

        # 6. Vigilante's independent kill. Uses are decremented here, based
        #    on the final submitted target, not at submit time — so
        #    changing your pick before Advance Phase doesn't burn a charge.
        vigilante_id = self._actor_id_for_kind(NightActionKind.VIGILANTE_KILL)
        vigilante_kill = self._night_actions.get(vigilante_id) if vigilante_id is not None else None
        if vigilante_id is not None and vigilante_kill is not None:
            self._vigilante_uses_remaining[vigilante_id] = (
                self._vigilante_uses_remaining.get(vigilante_id, 0) - 1
            )

        # 7. Doctor protects against the union of all pending kills so far.
        doctor_id = self._actor_id_for_kind(NightActionKind.DOCTOR_PROTECT)
        doctor_target = self._night_actions.get(doctor_id) if doctor_id is not None else None

        pending_kills = {
            target for target in (mafia_kill, sk_kill, vigilante_kill, bomb_kill) if target is not None
        }
        if doctor_target is not None:
            pending_kills.discard(doctor_target)

        # 8. Apply eliminations (a set naturally dedupes double-targeting).
        for target in pending_kills:
            self._alive[target] = False

        # 9. Terrorist arms a freshly planted bomb for next round, now that
        #    this round's bomb (if any) has resolved and the slot is free.
        #    Only present in `_night_actions` if step 2 found no old bomb
        #    pending at submit time — see `_submit_night_action`.
        if terrorist_id is not None:
            fresh_bomb_target = self._night_actions.get(terrorist_id)
            if fresh_bomb_target is not None:
                self._pending_bomb_target = fresh_bomb_target

        # 10. Clear all per-night deferred state.
        self._night_actions.clear()
        self._mafia_locked.clear()
        self._bomb_withdraw_requested = False

        killed = sorted(pending_kills)

        events: list[Event] = [
            PhaseChangedEvent(phase=self.phase, round_number=self._round_number),
            NightResultEvent(eliminated_player_ids=killed),
        ]
        if terrorist_id is not None:
            events.append(
                TerroristBombStatusEvent(
                    player_id=terrorist_id,
                    pending=self._pending_bomb_target is not None,
                    target_player_id=self._pending_bomb_target,
                )
            )

        # 11. Win check runs once, after all deaths are applied.
        winner = self._check_win()
        if winner is not None:
            self._machine.transition_to(MafiaPhase.GAME_OVER)
            events.append(GameOverEvent(winning_team=winner, roles=self._role_reveal()))
            return events

        self._machine.transition_to(MafiaPhase.DAY)
        return events

    def _resolve_mafia_kill(self) -> str | None:
        mafia_ids = [
            pid
            for pid, role in self._roles.items()
            if role.night_action_kind is NightActionKind.MAFIA_KILL and self.is_alive(pid)
        ]
        all_locked = bool(mafia_ids) and all(pid in self._mafia_locked for pid in mafia_ids)
        agreed_targets = {self._night_actions[pid] for pid in mafia_ids} if all_locked else set()

        if all_locked and len(agreed_targets) == 1:
            return next(iter(agreed_targets))
        if self._conflict_resolution is ConflictResolution.NO_KILL:
            return None
        # KILL_ANY: mafia failed to reach consensus, a random living player
        # dies instead — mafia included — raising the stakes of not
        # coordinating rather than defaulting to a safe no-kill.
        alive_ids = [pid for pid, alive in self._alive.items() if alive]
        return self._rng.choice(alive_ids) if alive_ids else None

    def _actor_id_for_kind(self, kind: NightActionKind) -> str | None:
        """Each special Town/Neutral role has at most one living instance
        per game (v1 simplification), so there's at most one actor for any
        night-action kind other than MAFIA_KILL (team-wide, handled
        separately by `_resolve_mafia_kill`).
        """
        for player_id, role in self._roles.items():
            if role.night_action_kind is kind and self.is_alive(player_id):
                return player_id
        return None

    def _resolve_voting(self) -> list[Event]:
        eliminated = self._plurality_target()
        if eliminated is not None:
            self._alive[eliminated] = False
        self._votes.clear()
        self._last_election_result = eliminated

        self._machine.transition_to(MafiaPhase.ELIMINATION)
        return [
            PhaseChangedEvent(phase=self.phase, round_number=self._round_number),
            EliminationResultEvent(eliminated_player_id=eliminated),
        ]

    def _plurality_target(self) -> str | None:
        """Whichever target has the most vote weight — a revealed Mayor's
        vote counts double. Ties are resolved per `self._day_tie_resolution`
        rather than an arbitrary winner, since a real vote wouldn't resolve
        one either.
        """
        if not self._votes:
            return None
        tally: dict[str, int] = {}
        for voter_id, target in self._votes.items():
            voter_role = self._roles.get(voter_id)
            weight = 2 if self._mayor_revealed and voter_role is not None and voter_role.key == "mayor" else 1
            tally[target] = tally.get(target, 0) + weight
        top_count = max(tally.values())
        leaders = sorted(target for target, count in tally.items() if count == top_count)
        if len(leaders) == 1:
            return leaders[0]
        if self._day_tie_resolution is DayTieResolution.RANDOM_AMONG_TIED:
            return self._rng.choice(leaders)
        return None

    def _resolve_elimination(self) -> list[Event]:
        winner = self._check_win(just_eliminated_by_vote=self._last_election_result)
        self._last_election_result = None
        if winner is not None:
            self._machine.transition_to(MafiaPhase.GAME_OVER)
            return [
                PhaseChangedEvent(phase=self.phase, round_number=self._round_number),
                GameOverEvent(winning_team=winner, roles=self._role_reveal()),
            ]

        self._machine.transition_to(MafiaPhase.NIGHT)
        self._round_number += 1
        return [PhaseChangedEvent(phase=self.phase, round_number=self._round_number)]

    def _role_reveal(self) -> list[PlayerRoleReveal]:
        return [
            PlayerRoleReveal(
                player_id=player_id,
                role_key=role.key,
                role_display_name=role.display_name,
                team=role.team.value,
            )
            for player_id, role in self._roles.items()
        ]

    def _check_win(self, just_eliminated_by_vote: str | None = None) -> str | None:
        if just_eliminated_by_vote is not None:
            eliminated_role = self._roles.get(just_eliminated_by_vote)
            if eliminated_role is not None and eliminated_role.key == "jester":
                return "jester"

        alive_ids = [player_id for player_id, alive in self._alive.items() if alive]
        alive_roles = [self._roles[player_id] for player_id in alive_ids]
        mafia_alive = sum(1 for role in alive_roles if role.team is Team.MAFIA)
        town_alive = sum(1 for role in alive_roles if role.team is Team.TOWN)
        hostile_neutral_alive = any(role.hostile for role in alive_roles)

        if len(alive_ids) == 1 and alive_roles[0].hostile:
            return alive_roles[0].key

        if hostile_neutral_alive:
            # A living hostile neutral (e.g. Serial Killer) blocks both
            # Town's and Mafia's win — the game keeps going until they're
            # eliminated or they win outright above.
            return None

        if mafia_alive == 0 and town_alive == 0:
            return "draw"
        if mafia_alive == 0:
            return "town"
        if mafia_alive >= town_alive:
            return "mafia"
        return None

    def phase_snapshot(self) -> dict[str, object]:
        return {
            "phase": self.phase.value,
            "round_number": self._round_number,
            "alive_player_ids": sorted(player_id for player_id, alive in self._alive.items() if alive),
        }
