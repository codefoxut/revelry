from __future__ import annotations

import random
from collections import Counter

from app.game_engine.base import Command, Event, GameEngine
from app.games.spyfall.commands import (
    AdvancePhaseCommand,
    CastVoteCommand,
    GuessLocationCommand,
    StartGameCommand,
)
from app.games.spyfall.events import (
    GameOverEvent,
    PhaseChangedEvent,
    PlayerRoleReveal,
    RoleAssignedEvent,
    VoteCastEvent,
)
from app.games.spyfall.location_assignment import assign_roles
from app.games.spyfall.locations import LOCATION_REGISTRY
from app.games.spyfall.phases import SPYFALL_TRANSITIONS, SpyfallPhase
from app.platform.exceptions import InvalidGameStateError
from app.platform.state_machine import StateMachine

_ROUND_NUMBER = 1


class SpyfallGameEngine(GameEngine):
    """Pure game-rules for a single round of Spyfall. No networking, no
    Room/RoomManager knowledge — GameSessionManager is the only caller and
    is responsible for translating Room state into `active_player_ids` and
    enforcing who's allowed to issue which command (host-only, etc).
    """

    def __init__(self, room_code: str, rng: random.Random | None = None) -> None:
        self.room_code = room_code
        self._rng = rng or random.Random()
        self._state_machine = StateMachine(SpyfallPhase.LOBBY, SPYFALL_TRANSITIONS)
        self._active_player_ids: list[str] = []
        self._location_key: str | None = None
        self._roles_by_player: dict[str, str | None] = {}
        self._votes_by_player: dict[str, str] = {}

    @property
    def phase(self) -> SpyfallPhase:
        return self._state_machine.phase

    async def handle_command(self, command: Command) -> list[Event]:
        if isinstance(command, StartGameCommand):
            return self._start_game(command)
        if isinstance(command, AdvancePhaseCommand):
            return self._advance_phase()
        if isinstance(command, CastVoteCommand):
            return self._cast_vote(command)
        if isinstance(command, GuessLocationCommand):
            return self._guess_location(command)
        raise InvalidGameStateError(f"Unsupported command: {type(command).__name__}")

    def phase_snapshot(self) -> dict[str, object]:
        return {
            "phase": self._state_machine.phase.value,
            "round_number": _ROUND_NUMBER,
            "alive_player_ids": list(self._active_player_ids),
        }

    def get_assignment(self, player_id: str) -> tuple[bool, str | None, str | None]:
        """Returns `(is_spy, location, role)` for `player_id`. Spyfall's
        equivalent of Mafia's GameSessionManager.get_role() accessor — the
        WS layer calls this to resend a reconnecting player their own
        private assignment.
        """
        if player_id not in self._roles_by_player:
            raise InvalidGameStateError(f"No assignment for player {player_id!r}")
        role = self._roles_by_player[player_id]
        is_spy = role is None
        location = None if is_spy else self._location(self._location_key)
        return is_spy, location, role

    def _location(self, location_key: str | None) -> str | None:
        if location_key is None:
            return None
        return LOCATION_REGISTRY[location_key].display_name

    def _spy_player_ids(self) -> list[str]:
        return [player_id for player_id, role in self._roles_by_player.items() if role is None]

    def _start_game(self, command: StartGameCommand) -> list[Event]:
        self._state_machine.transition_to(SpyfallPhase.DISCUSSION)
        self._active_player_ids = list(command.active_player_ids)
        self._location_key, self._roles_by_player = assign_roles(
            self._active_player_ids, self._rng, command.enabled_location_keys
        )

        events: list[Event] = [PhaseChangedEvent(phase=SpyfallPhase.DISCUSSION, round_number=_ROUND_NUMBER)]
        location_name = self._location(self._location_key)
        for player_id in self._active_player_ids:
            role = self._roles_by_player[player_id]
            events.append(
                RoleAssignedEvent(
                    player_id=player_id,
                    is_spy=role is None,
                    location=None if role is None else location_name,
                    role=role,
                )
            )
        return events

    def _advance_phase(self) -> list[Event]:
        if self._state_machine.phase == SpyfallPhase.DISCUSSION:
            self._state_machine.transition_to(SpyfallPhase.VOTING)
            return [PhaseChangedEvent(phase=SpyfallPhase.VOTING, round_number=_ROUND_NUMBER)]
        if self._state_machine.phase == SpyfallPhase.VOTING:
            return self._resolve_voting()
        raise InvalidGameStateError(f"Cannot advance phase from {self._state_machine.phase.value}")

    def _cast_vote(self, command: CastVoteCommand) -> list[Event]:
        if self._state_machine.phase != SpyfallPhase.VOTING:
            raise InvalidGameStateError("Votes can only be cast during voting")
        if command.target_player_id not in self._active_player_ids:
            raise InvalidGameStateError(f"Unknown vote target: {command.target_player_id!r}")
        self._votes_by_player[command.player_id] = command.target_player_id
        return [VoteCastEvent(player_id=command.player_id, target_player_id=command.target_player_id)]

    def _guess_location(self, command: GuessLocationCommand) -> list[Event]:
        if self._state_machine.phase not in (SpyfallPhase.DISCUSSION, SpyfallPhase.VOTING):
            raise InvalidGameStateError("Location can only be guessed during discussion or voting")
        spy_ids = self._spy_player_ids()
        if command.player_id not in spy_ids:
            raise InvalidGameStateError("Only the spy may guess the location")
        if command.location_key not in LOCATION_REGISTRY:
            raise InvalidGameStateError(f"Unknown location key: {command.location_key!r}")

        guessed_correctly = command.location_key == self._location_key
        winning_side = "spies" if guessed_correctly else "non_spies"
        self._state_machine.transition_to(SpyfallPhase.GAME_OVER)
        return [
            PhaseChangedEvent(phase=SpyfallPhase.GAME_OVER, round_number=_ROUND_NUMBER),
            self._build_game_over_event(winning_side=winning_side, accused_player_id=None),
        ]

    def _resolve_voting(self) -> list[Event]:
        accused_player_id = self._plurality_vote()
        spy_ids = set(self._spy_player_ids())
        was_spy = accused_player_id is not None and accused_player_id in spy_ids
        winning_side = "non_spies" if was_spy else "spies"

        self._state_machine.transition_to(SpyfallPhase.GAME_OVER)
        return [
            PhaseChangedEvent(phase=SpyfallPhase.GAME_OVER, round_number=_ROUND_NUMBER),
            self._build_game_over_event(winning_side=winning_side, accused_player_id=accused_player_id),
        ]

    def _plurality_vote(self) -> str | None:
        """Returns the player with the most votes, or None if there were no
        votes cast or the top spot is tied between two or more players — a
        tie means the room failed to reach consensus, so the spy evades by
        default (mirrors Mafia's "no clear plurality" tie handling).
        """
        if not self._votes_by_player:
            return None
        tally = Counter(self._votes_by_player.values())
        top_count = max(tally.values())
        leaders = [player_id for player_id, count in tally.items() if count == top_count]
        return leaders[0] if len(leaders) == 1 else None

    def _build_game_over_event(self, *, winning_side: str, accused_player_id: str | None) -> GameOverEvent:
        return GameOverEvent(
            winning_side=winning_side,
            location=self._location(self._location_key) or "",
            spy_player_ids=self._spy_player_ids(),
            accused_player_id=accused_player_id,
            reveals=[
                PlayerRoleReveal(player_id=player_id, is_spy=role is None, role=role)
                for player_id, role in self._roles_by_player.items()
            ],
        )
