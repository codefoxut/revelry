from app.game_engine.base import Command, Event, GameEngine
from app.games.mafia.commands import AdvancePhaseCommand, StartGameCommand
from app.games.mafia.events import PhaseChangedEvent
from app.games.mafia.phases import MAFIA_TRANSITIONS, MafiaPhase
from app.platform.exceptions import InvalidGameStateError
from app.platform.state_machine import StateMachine

# Phase reached by advancing past ELIMINATION, absent a win-check to decide
# otherwise. Step 11 replaces this with real win-condition logic that picks
# NIGHT or GAME_OVER.
_DEFAULT_POST_ELIMINATION_PHASE = MafiaPhase.NIGHT


class MafiaGameEngine(GameEngine):
    """Drives Mafia's phase sequence via the generic StateMachine. One
    instance lives per active game (constructed by GameSessionManager via
    the GameRegistry's engine_factory), so it holds its own in-memory state
    rather than round-tripping through a store on every command.

    No role/vote/win-condition knowledge yet — that's steps 10 and 11.
    """

    def __init__(self, room_code: str) -> None:
        self.room_code = room_code
        self._machine = StateMachine(MafiaPhase.LOBBY, MAFIA_TRANSITIONS)
        self._round_number = 0

    @property
    def phase(self) -> MafiaPhase:
        return self._machine.phase

    @property
    def round_number(self) -> int:
        return self._round_number

    async def handle_command(self, command: Command) -> list[Event]:
        if isinstance(command, StartGameCommand):
            return self._start_game()
        if isinstance(command, AdvancePhaseCommand):
            return self._advance_phase()
        raise ValueError(f"Unsupported command: {type(command).__name__}")

    def _start_game(self) -> list[Event]:
        self._machine.transition_to(MafiaPhase.NIGHT)
        self._round_number = 1
        return [PhaseChangedEvent(phase=self.phase, round_number=self._round_number)]

    def _advance_phase(self) -> list[Event]:
        current = self.phase
        if current is MafiaPhase.LOBBY:
            raise InvalidGameStateError("Game hasn't started yet")
        if current is MafiaPhase.GAME_OVER:
            raise InvalidGameStateError("Game is already over")

        next_phase = _DEFAULT_POST_ELIMINATION_PHASE if current is MafiaPhase.ELIMINATION else _NEXT_PHASE[current]
        self._machine.transition_to(next_phase)
        if next_phase is MafiaPhase.NIGHT:
            self._round_number += 1
        return [PhaseChangedEvent(phase=self.phase, round_number=self._round_number)]

    def phase_snapshot(self) -> dict[str, object]:
        return {"phase": self.phase.value, "round_number": self._round_number}


_NEXT_PHASE: dict[MafiaPhase, MafiaPhase] = {
    MafiaPhase.NIGHT: MafiaPhase.DAY,
    MafiaPhase.DAY: MafiaPhase.VOTING,
    MafiaPhase.VOTING: MafiaPhase.ELIMINATION,
}
