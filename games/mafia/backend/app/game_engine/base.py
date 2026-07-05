from abc import ABC, abstractmethod

from pydantic import BaseModel


class Command(BaseModel):
    """Base type for an intent sent into a GameEngine (e.g. CastVote, UseRole).

    Produced by translating a validated, permission-checked WebSocket event.
    The engine never sees WebSockets directly — only Commands — which keeps
    it reusable by bots, CLI tools, and automated simulations.
    """

    player_id: str


class Event(BaseModel):
    """Base type for something a GameEngine emits as a result of a command
    (e.g. PlayerEliminated, PhaseChanged). The networking layer translates
    these into WebSocket broadcasts; the engine has no knowledge of that.
    """


class GameEngine(ABC):
    """Pure game-rules interface. No networking, no I/O — reusable by human
    players, bots, and automated tests alike.
    """

    @abstractmethod
    async def handle_command(self, command: Command) -> list[Event]: ...

    @abstractmethod
    def phase_snapshot(self) -> dict[str, object]:
        """A JSON-serializable `{"phase": ..., "round_number": ...}`-shaped
        view of where the game currently is, for the room_state broadcast.
        Every phase-driven game has *a* current phase and *a* round/turn
        counter, so this stays in the base interface rather than leaking a
        Mafia-specific type into code that should stay game-agnostic.
        """
