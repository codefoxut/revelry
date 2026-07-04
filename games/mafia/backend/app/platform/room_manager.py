from __future__ import annotations

import secrets
import string
import uuid

from app.config import get_settings
from app.platform.exceptions import PermissionDeniedError, RoomFullError, RoomNotFoundError
from app.platform.room import Player, Room, RoomPhase
from app.platform.stores.in_memory import InMemoryStore
from app.platform.stores.room_store import RoomStore

_CODE_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0O1IL")
_CODE_LENGTH = 5
_MAX_PLAYERS = 20


class RoomManager:
    """Owns room lifecycle — create/join/leave/kick/host-migration. Depends
    only on RoomStore, never on a raw dict, so a future Redis-backed store
    can replace the in-memory one without any change here. Reusable by any
    future Revelry game, not just Mafia.
    """

    def __init__(self, room_store: RoomStore) -> None:
        self._room_store = room_store

    async def _generate_unique_code(self) -> str:
        while True:
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
            if not await self._room_store.exists(code):
                return code

    async def create_room(
        self,
        game_type: str,
        host_display_name: str,
        host_avatar: str = "default",
        is_private: bool = False,
    ) -> tuple[Room, str]:
        code = await self._generate_unique_code()
        host_id = str(uuid.uuid4())
        host = Player(id=host_id, display_name=host_display_name, avatar=host_avatar, is_host=True)

        room = Room(
            code=code,
            game_type=game_type,
            host_player_id=host_id,
            is_private=is_private,
            max_players=_MAX_PLAYERS,
        )
        room.players[host_id] = host

        await self._room_store.save(room)
        return room, host_id

    async def get_room(self, code: str) -> Room | None:
        return await self._room_store.get(code)

    async def require_room(self, code: str) -> Room:
        room = await self.get_room(code)
        if room is None:
            raise RoomNotFoundError(f"No room with code {code!r}")
        return room

    async def join_room(
        self,
        code: str,
        display_name: str,
        avatar: str = "default",
        as_spectator: bool = False,
    ) -> tuple[Room, str]:
        room = await self.require_room(code)

        # A game already in progress can only be joined as a spectator —
        # regardless of what the caller asked for.
        join_as_spectator = as_spectator or room.phase != RoomPhase.LOBBY
        if not join_as_spectator and room.active_player_count >= room.max_players:
            raise RoomFullError(f"Room {code!r} is full")

        player_id = str(uuid.uuid4())
        room.players[player_id] = Player(
            id=player_id,
            display_name=display_name,
            avatar=avatar,
            is_spectator=join_as_spectator,
        )
        await self._room_store.save(room)
        return room, player_id

    async def leave_room(self, code: str, player_id: str) -> Room | None:
        room = await self.require_room(code)
        room.players.pop(player_id, None)

        if not room.players:
            await self._room_store.delete(code)
            return None

        if room.host_player_id == player_id:
            self._migrate_host(room)

        await self._room_store.save(room)
        return room

    async def kick_player(self, code: str, requester_id: str, target_id: str) -> Room:
        room = await self.require_room(code)
        if room.host_player_id != requester_id:
            raise PermissionDeniedError("Only the host can kick players")
        if target_id == requester_id:
            raise PermissionDeniedError("The host cannot kick themself")

        room.players.pop(target_id, None)
        await self._room_store.save(room)
        return room

    def _migrate_host(self, room: Room) -> None:
        """Promote the longest-present remaining player to host."""
        next_host = next(iter(room.players.values()), None)
        if next_host is None:
            return
        room.host_player_id = next_host.id
        next_host.is_host = True

    def build_invite_url(self, code: str) -> str:
        settings = get_settings()
        return f"{settings.frontend_base_url.rstrip('/')}/room/{code}"


room_store = RoomStore(InMemoryStore())
room_manager = RoomManager(room_store)
