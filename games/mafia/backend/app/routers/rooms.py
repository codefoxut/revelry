from fastapi import APIRouter, Depends, HTTPException, status

from app.platform.room import Room
from app.platform.room_manager import RoomManager, room_manager
from app.schemas.room import CreateRoomRequest, CreateRoomResponse, PlayerOut, RoomOut, RoomSummary

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


def get_room_manager() -> RoomManager:
    return room_manager


def _to_room_out(room: Room, manager: RoomManager) -> RoomOut:
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
        invite_url=manager.build_invite_url(room.code),
    )


@router.post("", response_model=CreateRoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    payload: CreateRoomRequest,
    manager: RoomManager = Depends(get_room_manager),
) -> CreateRoomResponse:
    room, host_id = await manager.create_room(
        game_type=payload.game_type,
        host_display_name=payload.host_display_name,
        host_avatar=payload.host_avatar,
        is_private=payload.is_private,
    )
    return CreateRoomResponse(room=_to_room_out(room, manager), player_id=host_id)


@router.get("/{code}", response_model=RoomSummary)
async def get_room_summary(
    code: str,
    manager: RoomManager = Depends(get_room_manager),
) -> RoomSummary:
    room = await manager.get_room(code.upper())
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    return RoomSummary(
        code=room.code,
        game_type=room.game_type,
        phase=room.phase.value,
        is_private=room.is_private,
        player_count=room.active_player_count,
        max_players=room.max_players,
    )
