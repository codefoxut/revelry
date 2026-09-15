from abc import ABC, abstractmethod

from pydantic import BaseModel


class Command(BaseModel):
    """Base type for an intent sent into a GameEngine."""

    player_id: str


class Event(BaseModel):
    """Base type for something a GameEngine emits as a result of a command."""


class GameEngine(ABC):
    """Pure game-rules interface. No networking, no I/O."""

    @abstractmethod
    async def handle_command(self, command: Command) -> list[Event]: ...

    @abstractmethod
    def phase_snapshot(self) -> dict[str, object]: ...
