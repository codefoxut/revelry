from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.platform.disconnect_grace import DisconnectGraceManager
from app.platform.game_session_manager import GameSessionManager, game_session_manager as _game_session_manager
from app.platform.room import RoomPhase
from app.platform.room_manager import RoomManager
from app.routers.rooms import get_room_manager
from app.schemas.room import RoleOut
from app.schemas.ws_events import PlayerConnectionChangedEvent, RoleAssignedEvent, RoomStateEvent
from app.services.room_presenter import to_room_out
from app.websocket.connection_manager import ConnectionManager
from app.websocket.dispatcher import dispatch_client_event

router = APIRouter()

_connection_manager = ConnectionManager()
_disconnect_grace_manager = DisconnectGraceManager()

# Codes above 4000 are the application-reserved range for WS close codes.
_CLOSE_ROOM_OR_PLAYER_NOT_FOUND = 4404


def get_connection_manager() -> ConnectionManager:
    return _connection_manager


def get_game_session_manager() -> GameSessionManager:
    return _game_session_manager


def get_disconnect_grace_manager() -> DisconnectGraceManager:
    return _disconnect_grace_manager


@router.websocket("/ws/{room_code}")
async def room_socket(
    websocket: WebSocket,
    room_code: str,
    player_id: str,
    manager: RoomManager = Depends(get_room_manager),
    connections: ConnectionManager = Depends(get_connection_manager),
    games: GameSessionManager = Depends(get_game_session_manager),
    grace: DisconnectGraceManager = Depends(get_disconnect_grace_manager),
) -> None:
    room_code = room_code.upper()
    room = await manager.get_room(room_code)
    if room is None or player_id not in room.players:
        await websocket.close(code=_CLOSE_ROOM_OR_PLAYER_NOT_FOUND)
        return

    grace.cancel(room_code, player_id)
    await connections.connect(room_code, player_id, websocket)
    room.players[player_id].connected = True

    invite_url = manager.build_invite_url(room_code)
    game_state = await games.get_phase_snapshot(room_code)
    await connections.send_to_player(
        room_code, player_id, RoomStateEvent(room=to_room_out(room, invite_url, game_state))
    )

    role = await games.get_role(room_code, player_id)
    if role is not None:
        await connections.send_to_player(
            room_code,
            player_id,
            RoleAssignedEvent(
                role=RoleOut(
                    key=role.key,
                    display_name=role.display_name,
                    team=role.team.value,
                    description=role.description,
                    acts_at_night=role.acts_at_night,
                )
            ),
        )

    await connections.broadcast(
        room_code,
        PlayerConnectionChangedEvent(player_id=player_id, connected=True),
        exclude_player_id=player_id,
    )

    try:
        while True:
            raw_event = await websocket.receive_json()
            should_close = await dispatch_client_event(
                raw_event,
                room_code=room_code,
                player_id=player_id,
                room_manager=manager,
                connection_manager=connections,
                game_session_manager=games,
            )
            if should_close:
                await websocket.close(code=1000)
                return
    except WebSocketDisconnect:
        connections.disconnect(room_code, player_id)
        room = await manager.get_room(room_code)
        if room is not None and player_id in room.players:
            room.players[player_id].connected = False
            await connections.broadcast(
                room_code,
                PlayerConnectionChangedEvent(player_id=player_id, connected=False),
            )
            if room.phase == RoomPhase.LOBBY:
                grace.schedule_removal(room_code, player_id, manager, connections, games)
