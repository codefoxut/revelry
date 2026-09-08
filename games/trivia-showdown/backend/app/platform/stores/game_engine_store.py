from app.game_engine.base import GameEngine
from app.platform.stores.base import KeyValueStore


class GameEngineStore:
    """Typed wrapper over a KeyValueStore for the one live GameEngine
    instance per room, keyed by room code. Same shape as RoomStore.
    """

    def __init__(self, backend: KeyValueStore[GameEngine]) -> None:
        self._backend = backend

    async def get(self, room_code: str) -> GameEngine | None:
        return await self._backend.get(room_code)

    async def save(self, room_code: str, engine: GameEngine) -> None:
        await self._backend.set(room_code, engine)

    async def delete(self, room_code: str) -> None:
        await self._backend.delete(room_code)
