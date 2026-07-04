from app.platform.room import Room
from app.schemas.room import GameStateOut, PlayerOut, RoomOut


def to_room_out(room: Room, invite_url: str, game_state: dict[str, object] | None = None) -> RoomOut:
    """Map the in-memory Room domain object to its public API shape.

    Shared between the REST router and the WebSocket layer so both send an
    identically-shaped room snapshot. `game_state` is the active game
    engine's `phase_snapshot()` output, if any (None while still in lobby).
    """
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
