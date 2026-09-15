from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class KeyValueStore(ABC, Generic[T]):
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
