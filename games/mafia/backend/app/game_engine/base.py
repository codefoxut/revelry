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
