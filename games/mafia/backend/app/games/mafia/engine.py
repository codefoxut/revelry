import random

from app.game_engine.base import Command, Event, GameEngine
from app.games.mafia.commands import (
    AdvancePhaseCommand,
    CastVoteCommand,
    StartGameCommand,
    SubmitNightActionCommand,
)
from app.games.mafia.events import (
    EliminationResultEvent,
    GameOverEvent,
    InvestigationResultEvent,
    NightResultEvent,
    PhaseChangedEvent,
    RoleAssignedEvent,
)
from app.games.mafia.phases import MAFIA_TRANSITIONS, MafiaPhase
from app.games.mafia.role_assignment import assign_roles
from app.games.mafia.roles import Role, Team
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
        self._mafia_votes: dict[str, str] = {}
        self._protect_target: str | None = None
        self._votes: dict[str, str] = {}

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
            return self._start_game(command.active_player_ids)
        if isinstance(command, AdvancePhaseCommand):
            return self._advance_phase()
        if isinstance(command, SubmitNightActionCommand):
            return self._submit_night_action(command.player_id, command.target_player_id)
        if isinstance(command, CastVoteCommand):
            return self._cast_vote(command.player_id, command.target_player_id)
        raise ValueError(f"Unsupported command: {type(command).__name__}")

    def _start_game(self, active_player_ids: list[str]) -> list[Event]:
        self._machine.transition_to(MafiaPhase.NIGHT)
        self._round_number = 1
        self._roles = assign_roles(active_player_ids, self._rng)
        self._alive = {player_id: True for player_id in active_player_ids}

        events: list[Event] = [PhaseChangedEvent(phase=self.phase, round_number=self._round_number)]
        events.extend(
            RoleAssignedEvent(
                player_id=player_id,
                role_key=role.key,
                role_display_name=role.display_name,
                team=role.team.value,
                description=role.description,
                acts_at_night=role.acts_at_night,
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

        if role.key == "mafia":
            self._mafia_votes[player_id] = target_player_id
            return []
        if role.key == "doctor":
            self._protect_target = target_player_id
            return []
        if role.key == "detective":
            target_role = self._roles[target_player_id]
            return [
                InvestigationResultEvent(
                    player_id=player_id, target_player_id=target_player_id, team=target_role.team.value
                )
            ]
        raise InvalidGameStateError(f"Role {role.key!r} has no night action handling")

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
        killed = _plurality_target(self._mafia_votes)
        if killed is not None and killed == self._protect_target:
            killed = None
        if killed is not None:
            self._alive[killed] = False
        self._mafia_votes.clear()
        self._protect_target = None

        winner = self._check_win()
        if winner is not None:
            self._machine.transition_to(MafiaPhase.GAME_OVER)
            return [
                PhaseChangedEvent(phase=self.phase, round_number=self._round_number),
                NightResultEvent(eliminated_player_id=killed),
                GameOverEvent(winning_team=winner.value),
            ]

        self._machine.transition_to(MafiaPhase.DAY)
        return [
            PhaseChangedEvent(phase=self.phase, round_number=self._round_number),
            NightResultEvent(eliminated_player_id=killed),
        ]

    def _resolve_voting(self) -> list[Event]:
        eliminated = _plurality_target(self._votes)
        if eliminated is not None:
            self._alive[eliminated] = False
        self._votes.clear()

        self._machine.transition_to(MafiaPhase.ELIMINATION)
        return [
            PhaseChangedEvent(phase=self.phase, round_number=self._round_number),
            EliminationResultEvent(eliminated_player_id=eliminated),
        ]

    def _resolve_elimination(self) -> list[Event]:
        winner = self._check_win()
        if winner is not None:
            self._machine.transition_to(MafiaPhase.GAME_OVER)
            return [
                PhaseChangedEvent(phase=self.phase, round_number=self._round_number),
                GameOverEvent(winning_team=winner.value),
            ]

        self._machine.transition_to(MafiaPhase.NIGHT)
        self._round_number += 1
        return [PhaseChangedEvent(phase=self.phase, round_number=self._round_number)]

    def _check_win(self) -> Team | None:
        alive_teams = [self._roles[player_id].team for player_id, alive in self._alive.items() if alive]
        mafia_alive = alive_teams.count(Team.MAFIA)
        town_alive = len(alive_teams) - mafia_alive
        if mafia_alive == 0:
            return Team.TOWN
        if mafia_alive >= town_alive:
            return Team.MAFIA
        return None

    def phase_snapshot(self) -> dict[str, object]:
        return {
            "phase": self.phase.value,
            "round_number": self._round_number,
            "alive_player_ids": sorted(player_id for player_id, alive in self._alive.items() if alive),
        }


def _plurality_target(votes: dict[str, str]) -> str | None:
    """Whichever target has the most votes; None (no result) on a tie or
    if no votes were cast. Ties broken by "no one" rather than an arbitrary
    winner, since a real vote wouldn't resolve one either.
    """
    if not votes:
        return None
    tally: dict[str, int] = {}
    for target in votes.values():
        tally[target] = tally.get(target, 0) + 1
    top_count = max(tally.values())
    leaders = [target for target, count in tally.items() if count == top_count]
    return leaders[0] if len(leaders) == 1 else None
