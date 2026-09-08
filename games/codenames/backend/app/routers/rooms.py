from fastapi import APIRouter, Depends, HTTPException, status

from app.platform.exceptions import RoomFullError, RoomNotFoundError
from app.platform.room_manager import RoomManager, room_manager
from app.schemas.room import CreateRoomRequest, CreateRoomResponse, JoinRoomRequest, RoomSummary
from app.services.room_presenter import to_room_out

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


def get_room_manager() -> RoomManager:
    return room_manager


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
    invite_url = manager.build_invite_url(room.code)
    return CreateRoomResponse(room=to_room_out(room, invite_url), player_id=host_id)


@router.post("/{code}/join", response_model=CreateRoomResponse)
async def join_room(
    code: str,
    payload: JoinRoomRequest,
    manager: RoomManager = Depends(get_room_manager),
) -> CreateRoomResponse:
    try:
        room, player_id = await manager.join_room(
            code.upper(),
            display_name=payload.display_name,
            avatar=payload.avatar,
            as_spectator=payload.as_spectator,
        )
    except RoomNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found") from exc
    except RoomFullError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Room is full") from exc

    invite_url = manager.build_invite_url(room.code)
    return CreateRoomResponse(room=to_room_out(room, invite_url), player_id=player_id)


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
