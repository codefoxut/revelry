from __future__ import annotations

import asyncio

from app.platform.game_session_manager import GameSessionManager
from app.platform.room import RoomPhase
from app.platform.room_manager import RoomManager
from app.services.room_presenter import broadcast_room_state
from app.websocket.connection_manager import ConnectionManager

_DEFAULT_GRACE_SECONDS = 30.0


class DisconnectGraceManager:
    """Gives a disconnected player a grace window to reconnect before being
    dropped from the room, instead of losing their seat the instant a
    socket drops (a network blip or a page refresh shouldn't cost a spot).

    Only removes players while the room is still in the lobby. Once a game
    has started, a disconnected player's `Player.connected` flag just stays
    False indefinitely — removing them mid-game would desync the room's
    player list from the game engine's own alive/role bookkeeping, which is
    keyed by player_id and has no notion of "no longer in the room." Real
    reconnection into an in-progress game already works without this class,
    since a fresh WS connect with the same player_id just resends room
    state and any assigned role.
    """

    def __init__(self, grace_seconds: float = _DEFAULT_GRACE_SECONDS) -> None:
        self._grace_seconds = grace_seconds
        self._tasks: dict[tuple[str, str], asyncio.Task] = {}

    def schedule_removal(
        self,
        room_code: str,
        player_id: str,
        room_manager: RoomManager,
        connection_manager: ConnectionManager,
        game_session_manager: GameSessionManager,
    ) -> None:
        self.cancel(room_code, player_id)
        self._tasks[(room_code, player_id)] = asyncio.create_task(
            self._remove_after_delay(room_code, player_id, room_manager, connection_manager, game_session_manager)
        )

    def cancel(self, room_code: str, player_id: str) -> None:
        task = self._tasks.pop((room_code, player_id), None)
        if task is not None:
            task.cancel()

    def cancel_all(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    async def _remove_after_delay(
        self,
        room_code: str,
        player_id: str,
        room_manager: RoomManager,
        connection_manager: ConnectionManager,
        game_session_manager: GameSessionManager,
    ) -> None:
        await asyncio.sleep(self._grace_seconds)
        self._tasks.pop((room_code, player_id), None)

        room = await room_manager.get_room(room_code)
        if room is None or player_id not in room.players:
            return
        if room.phase != RoomPhase.LOBBY:
            return
        if room.players[player_id].connected:
            return

        remaining_room = await room_manager.leave_room(room_code, player_id)
        connection_manager.disconnect(room_code, player_id)
        if remaining_room is not None:
            await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)
