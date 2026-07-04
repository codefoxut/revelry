from __future__ import annotations

from app.games.mafia.events import (
    EliminationResultEvent as EngineEliminationResultEvent,
    GameOverEvent as EngineGameOverEvent,
    InvestigationResultEvent as EngineInvestigationResultEvent,
    NightResultEvent as EngineNightResultEvent,
)
from app.games.mafia.events import RoleAssignedEvent as EngineRoleAssignedEvent
from app.platform.exceptions import (
    GameAlreadyStartedError,
    GameNotStartedError,
    InvalidGameStateError,
    NotEnoughPlayersError,
    PermissionDeniedError,
    PlayerNotFoundError,
)
from app.platform.game_session_manager import GameSessionManager
from app.platform.room_manager import RoomManager
from app.schemas.room import RoleOut
from app.schemas.ws_events import (
    EliminationResultEvent,
    ErrorEvent,
    GameOverEvent,
    InvestigationResultEvent,
    KickedEvent,
    NightResultEvent,
    PongEvent,
    RoleAssignedEvent,
    VoteCastEvent,
)
from app.services.room_presenter import broadcast_room_state
from app.websocket.connection_manager import ConnectionManager

# Close code used when a host kicks another player from the room.
_CLOSE_KICKED = 4403


async def dispatch_client_event(
    raw_event: dict,
    *,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    connection_manager: ConnectionManager,
    game_session_manager: GameSessionManager,
) -> bool:
    """Route one parsed client message to its handler.

    Returns True when the caller's WS receive loop should stop and close
    the socket itself (a voluntary leave) — needed because a handler can't
    safely close its own connection's socket mid-receive-loop from within
    the same task. Grows a branch per command as later steps add game and
    chat commands — kept as a plain dispatch table rather than a class
    since there's no shared state beyond what's passed in.
    """
    event_type = raw_event.get("type")

    if event_type == "ping":
        await connection_manager.send_to_player(room_code, player_id, PongEvent())
        return False

    if event_type == "set_ready":
        await _handle_set_ready(raw_event, room_code, player_id, room_manager, connection_manager, game_session_manager)
        return False

    if event_type == "update_profile":
        await _handle_update_profile(raw_event, room_code, player_id, room_manager, connection_manager, game_session_manager)
        return False

    if event_type == "kick_player":
        await _handle_kick_player(raw_event, room_code, player_id, room_manager, connection_manager, game_session_manager)
        return False

    if event_type == "leave_room":
        await _handle_leave_room(room_code, player_id, room_manager, connection_manager, game_session_manager)
        return True

    if event_type == "start_game":
        await _handle_start_game(room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "advance_phase":
        await _handle_advance_phase(room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "night_action":
        await _handle_night_action(raw_event, room_code, player_id, game_session_manager, connection_manager)
        return False

    if event_type == "cast_vote":
        await _handle_cast_vote(raw_event, room_code, player_id, game_session_manager, connection_manager)
        return False

    await _send_error(connection_manager, room_code, player_id, "unknown_event", f"Unrecognized event type: {event_type!r}")
    return False


async def _handle_set_ready(
    raw_event: dict,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    connection_manager: ConnectionManager,
    game_session_manager: GameSessionManager,
) -> None:
    ready = raw_event.get("ready")
    if not isinstance(ready, bool):
        await _send_error(connection_manager, room_code, player_id, "invalid_payload", "`ready` must be a boolean")
        return

    try:
        await room_manager.set_ready(room_code, player_id, ready)
    except PlayerNotFoundError as exc:
        await _send_error(connection_manager, room_code, player_id, "player_not_found", str(exc))
        return

    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_update_profile(
    raw_event: dict,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    connection_manager: ConnectionManager,
    game_session_manager: GameSessionManager,
) -> None:
    display_name = raw_event.get("display_name")
    avatar = raw_event.get("avatar")
    if display_name is None and avatar is None:
        await _send_error(
            connection_manager,
            room_code,
            player_id,
            "invalid_payload",
            "At least one of `display_name` or `avatar` is required",
        )
        return

    try:
        await room_manager.update_profile(room_code, player_id, display_name=display_name, avatar=avatar)
    except PlayerNotFoundError as exc:
        await _send_error(connection_manager, room_code, player_id, "player_not_found", str(exc))
        return

    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_kick_player(
    raw_event: dict,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    connection_manager: ConnectionManager,
    game_session_manager: GameSessionManager,
) -> None:
    target_id = raw_event.get("target_player_id")
    if not target_id:
        await _send_error(connection_manager, room_code, player_id, "invalid_payload", "`target_player_id` is required")
        return

    try:
        await room_manager.kick_player(room_code, requester_id=player_id, target_id=target_id)
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return

    await connection_manager.send_to_player(room_code, target_id, KickedEvent())
    await connection_manager.close(room_code, target_id, code=_CLOSE_KICKED)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_leave_room(
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    connection_manager: ConnectionManager,
    game_session_manager: GameSessionManager,
) -> None:
    remaining_room = await room_manager.leave_room(room_code, player_id)
    connection_manager.disconnect(room_code, player_id)
    if remaining_room is not None:
        await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_start_game(
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    try:
        _, events = await game_session_manager.start_game(room_code, player_id)
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
    except GameAlreadyStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_already_started", str(exc))
        return
    except NotEnoughPlayersError as exc:
        await _send_error(connection_manager, room_code, player_id, "not_enough_players", str(exc))
        return

    for event in events:
        if isinstance(event, EngineRoleAssignedEvent):
            await connection_manager.send_to_player(room_code, event.player_id, _to_ws_role_assigned(event))

    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_advance_phase(
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    try:
        events = await game_session_manager.advance_phase(room_code, player_id)
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return

    for event in events:
        if isinstance(event, EngineNightResultEvent):
            await connection_manager.broadcast(
                room_code, NightResultEvent(eliminated_player_id=event.eliminated_player_id)
            )
        elif isinstance(event, EngineEliminationResultEvent):
            await connection_manager.broadcast(
                room_code, EliminationResultEvent(eliminated_player_id=event.eliminated_player_id)
            )
        elif isinstance(event, EngineGameOverEvent):
            await connection_manager.broadcast(room_code, GameOverEvent(winning_team=event.winning_team))

    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_night_action(
    raw_event: dict,
    room_code: str,
    player_id: str,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    target_id = raw_event.get("target_player_id")
    if not target_id:
        await _send_error(connection_manager, room_code, player_id, "invalid_payload", "`target_player_id` is required")
        return

    try:
        events = await game_session_manager.submit_night_action(room_code, player_id, target_id)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return

    for event in events:
        if isinstance(event, EngineInvestigationResultEvent):
            await connection_manager.send_to_player(
                room_code,
                event.player_id,
                InvestigationResultEvent(target_player_id=event.target_player_id, team=event.team),
            )


async def _handle_cast_vote(
    raw_event: dict,
    room_code: str,
    player_id: str,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    target_id = raw_event.get("target_player_id")
    if not target_id:
        await _send_error(connection_manager, room_code, player_id, "invalid_payload", "`target_player_id` is required")
        return

    try:
        await game_session_manager.cast_vote(room_code, player_id, target_id)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return

    await connection_manager.broadcast(room_code, VoteCastEvent(player_id=player_id, target_player_id=target_id))


def _to_ws_role_assigned(event: EngineRoleAssignedEvent) -> RoleAssignedEvent:
    return RoleAssignedEvent(
        role=RoleOut(
            key=event.role_key,
            display_name=event.role_display_name,
            team=event.team,
            description=event.description,
            acts_at_night=event.acts_at_night,
        )
    )


async def _send_error(
    connection_manager: ConnectionManager,
    room_code: str,
    player_id: str,
    code: str,
    message: str,
) -> None:
    await connection_manager.send_to_player(room_code, player_id, ErrorEvent(code=code, message=message))
