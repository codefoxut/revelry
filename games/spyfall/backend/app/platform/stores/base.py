from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class KeyValueStore(ABC, Generic[T]):
    """Storage abstraction for active in-memory game state.

    Business logic (services, the game engine) must depend on this interface
    — or the typed wrappers built on top of it, e.g. RoomStore — never on a
    raw dict. That way a future Redis-backed implementation can replace
    InMemoryStore without any change to game logic.
    """

    @abstractmethod
    async def get(self, key: str) -> T | None: ...

    @abstractmethod
    async def set(self, key: str, value: T) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def keys(self) -> list[str]: ...
