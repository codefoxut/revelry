from app.platform.stores.base import KeyValueStore, T


class InMemoryStore(KeyValueStore[T]):
    """Dict-backed KeyValueStore. This is the only backend today (no Redis) —
    all active rooms/sessions/game state live in process memory.
    """

    def __init__(self) -> None:
        self._data: dict[str, T] = {}

    async def get(self, key: str) -> T | None:
        return self._data.get(key)

    async def set(self, key: str, value: T) -> None:
        self._data[key] = value

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._data

    async def keys(self) -> list[str]:
        return list(self._data.keys())
