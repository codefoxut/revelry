from __future__ import annotations

from typing import TYPE_CHECKING

from app.platform.room import Room
from app.schemas.room import GameStateOut, PlayerOut, RoomOut
from app.schemas.ws_events import RoomStateEvent

if TYPE_CHECKING:
    from app.platform.game_session_manager import GameSessionManager
    from app.platform.room_manager import RoomManager
    from app.websocket.connection_manager import ConnectionManager


def to_room_out(room: Room, invite_url: str, game_state: dict[str, object] | None = None) -> RoomOut:
    return RoomOut(
        code=room.code,
        game_type=room.game_type,
        is_private=room.is_private,
        phase=room.phase.value,
        max_players=room.max_players,
        players=[
            PlayerOut(
                id=player.id,
                display_name=player.display_name,
                avatar=player.avatar,
                is_host=player.is_host,
                is_ready=player.is_ready,
                is_spectator=player.is_spectator,
                connected=player.connected,
            )
            for player in room.players.values()
        ],
        invite_url=invite_url,
        game_state=GameStateOut(**game_state) if game_state is not None else None,
    )


async def broadcast_room_state(
    room_code: str,
    room_manager: "RoomManager",
    connection_manager: "ConnectionManager",
    game_session_manager: "GameSessionManager",
) -> None:
    room = await room_manager.require_room(room_code)
    invite_url = room_manager.build_invite_url(room_code)
    game_state = await game_session_manager.get_phase_snapshot(room_code)
    await connection_manager.broadcast(room_code, RoomStateEvent(room=to_room_out(room, invite_url, game_state)))
