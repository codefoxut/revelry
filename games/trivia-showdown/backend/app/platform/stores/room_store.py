from app.platform.room import Room
from app.platform.stores.base import KeyValueStore


class RoomStore:
    """Typed wrapper over a KeyValueStore for Room objects, keyed by room
    code. RoomManager is the only thing that should touch this — nothing
    else needs to know rooms are stored as a dict under the hood.
    """

    def __init__(self, backend: KeyValueStore[Room]) -> None:
        self._backend = backend

    async def get(self, code: str) -> Room | None:
        return await self._backend.get(code)

    async def save(self, room: Room) -> None:
        await self._backend.set(room.code, room)

    async def delete(self, code: str) -> None:
        await self._backend.delete(code)

    async def exists(self, code: str) -> bool:
        return await self._backend.exists(code)

    async def all_codes(self) -> list[str]:
        return await self._backend.keys()
