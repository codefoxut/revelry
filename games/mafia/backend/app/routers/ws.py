from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.platform.room_manager import RoomManager
from app.routers.rooms import get_room_manager
from app.schemas.ws_events import PlayerConnectionChangedEvent, RoomStateEvent
from app.services.room_presenter import to_room_out
from app.websocket.connection_manager import ConnectionManager
from app.websocket.dispatcher import dispatch_client_event

router = APIRouter()

_connection_manager = ConnectionManager()

# Codes above 4000 are the application-reserved range for WS close codes.
_CLOSE_ROOM_OR_PLAYER_NOT_FOUND = 4404


def get_connection_manager() -> ConnectionManager:
    return _connection_manager


@router.websocket("/ws/{room_code}")
async def room_socket(
    websocket: WebSocket,
    room_code: str,
    player_id: str,
    manager: RoomManager = Depends(get_room_manager),
    connections: ConnectionManager = Depends(get_connection_manager),
) -> None:
    room_code = room_code.upper()
    room = await manager.get_room(room_code)
    if room is None or player_id not in room.players:
        await websocket.close(code=_CLOSE_ROOM_OR_PLAYER_NOT_FOUND)
        return

    await connections.connect(room_code, player_id, websocket)
    room.players[player_id].connected = True

    invite_url = manager.build_invite_url(room_code)
    await connections.send_to_player(room_code, player_id, RoomStateEvent(room=to_room_out(room, invite_url)))
    await connections.broadcast(
        room_code,
        PlayerConnectionChangedEvent(player_id=player_id, connected=True),
        exclude_player_id=player_id,
    )

    try:
        while True:
            raw_event = await websocket.receive_json()
            await dispatch_client_event(
                raw_event,
                room_code=room_code,
                player_id=player_id,
                connection_manager=connections,
            )
    except WebSocketDisconnect:
        connections.disconnect(room_code, player_id)
        room = await manager.get_room(room_code)
        if room is not None and player_id in room.players:
            room.players[player_id].connected = False
            await connections.broadcast(
                room_code,
                PlayerConnectionChangedEvent(player_id=player_id, connected=False),
            )
