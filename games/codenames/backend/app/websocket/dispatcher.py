from __future__ import annotations

from app.games.spyfall.events import GameOverEvent as EngineGameOverEvent
from app.games.spyfall.events import PlayerRoleReveal as EnginePlayerRoleReveal
from app.games.spyfall.events import RoleAssignedEvent as EngineRoleAssignedEvent
from app.games.spyfall.locations import LOCATION_REGISTRY
from app.games.spyfall.phases import SpyfallPhase
from app.platform.exceptions import (
    GameAlreadyStartedError,
    GameNotStartedError,
    InvalidGameSettingsError,
    InvalidGameStateError,
    NotEnoughPlayersError,
    PermissionDeniedError,
    PlayerNotFoundError,
    RoomNotFoundError,
)
from app.platform.game_session_manager import GameSessionManager
from app.platform.night_timer import NightTimerManager
from app.platform.room_manager import RoomManager
from app.schemas.ws_events import (
    DiscussionTimerStartedEvent,
    ErrorEvent,
    GameOverEvent,
    KickedEvent,
    PlayerRoleRevealOut,
    PongEvent,
    RoleAssignedEvent,
    VoteCastEvent,
)
from app.services.room_presenter import broadcast_room_state
from app.websocket.connection_manager import ConnectionManager

# Close code used when a host kicks another player from the room.
_CLOSE_KICKED = 4403

_LOCATION_KEY_VALUES = set(LOCATION_REGISTRY.keys())


async def dispatch_client_event(
    raw_event: dict,
    *,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    connection_manager: ConnectionManager,
    game_session_manager: GameSessionManager,
    night_timer_manager: NightTimerManager,
) -> bool:
    """Route one parsed client message to its handler.

    Returns True when the caller's WS receive loop should stop and close
    the socket itself (a voluntary leave) — needed because a handler can't
    safely close its own connection's socket mid-receive-loop from within
    the same task. Kept as a plain dispatch table rather than a class since
    there's no shared state beyond what's passed in.
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
        await _handle_start_game(
            raw_event, room_code, player_id, room_manager, game_session_manager, connection_manager, night_timer_manager
        )
        return False

    if event_type == "advance_phase":
        await _handle_advance_phase(
            room_code, player_id, room_manager, game_session_manager, connection_manager, night_timer_manager
        )
        return False

    if event_type == "cast_vote":
        await _handle_cast_vote(raw_event, room_code, player_id, game_session_manager, connection_manager)
        return False

    if event_type == "guess_location":
        await _handle_guess_location(
            raw_event, room_code, player_id, room_manager, game_session_manager, connection_manager, night_timer_manager
        )
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
    raw_event: dict,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
    night_timer_manager: NightTimerManager,
) -> None:
    enabled_location_keys_raw = raw_event.get("enabled_location_keys")
    if enabled_location_keys_raw is not None:
        if not isinstance(enabled_location_keys_raw, list) or not all(
            key in _LOCATION_KEY_VALUES for key in enabled_location_keys_raw
        ):
            await _send_error(
                connection_manager,
                room_code,
                player_id,
                "invalid_payload",
                f"`enabled_location_keys` must be a list from {sorted(_LOCATION_KEY_VALUES)}",
            )
            return

    try:
        _, events = await game_session_manager.start_game(
            room_code,
            player_id,
            frozenset(enabled_location_keys_raw) if enabled_location_keys_raw is not None else None,
        )
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
    except GameAlreadyStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_already_started", str(exc))
        return
    except NotEnoughPlayersError as exc:
        await _send_error(connection_manager, room_code, player_id, "not_enough_players", str(exc))
        return
    except InvalidGameSettingsError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_settings", str(exc))
        return

    for event in events:
        if isinstance(event, EngineRoleAssignedEvent):
            await connection_manager.send_to_player(room_code, event.player_id, _to_ws_role_assigned(event))

    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)
    await _sync_discussion_timer(room_code, room_manager, connection_manager, game_session_manager, night_timer_manager)


async def _handle_advance_phase(
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
    night_timer_manager: NightTimerManager,
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

    await _broadcast_resolution_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)
    await _sync_discussion_timer(room_code, room_manager, connection_manager, game_session_manager, night_timer_manager)


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


async def _handle_guess_location(
    raw_event: dict,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
    night_timer_manager: NightTimerManager,
) -> None:
    location_key = raw_event.get("location_key")
    if not location_key or location_key not in _LOCATION_KEY_VALUES:
        await _send_error(
            connection_manager,
            room_code,
            player_id,
            "invalid_payload",
            f"`location_key` must be one of {sorted(_LOCATION_KEY_VALUES)}",
        )
        return

    try:
        events = await game_session_manager.guess_location(room_code, player_id, location_key)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return

    await _broadcast_resolution_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)
    await _sync_discussion_timer(room_code, room_manager, connection_manager, game_session_manager, night_timer_manager)


async def _broadcast_resolution_events(events: list, room_code: str, connection_manager: ConnectionManager) -> None:
    for event in events:
        if isinstance(event, EngineGameOverEvent):
            await connection_manager.broadcast(room_code, _to_ws_game_over(event))


async def _sync_discussion_timer(
    room_code: str,
    room_manager: RoomManager,
    connection_manager: ConnectionManager,
    game_session_manager: GameSessionManager,
    night_timer_manager: NightTimerManager,
) -> None:
    """Always cancels any pending timer for this room first, then reschedules
    one iff the game is currently sitting in DISCUSSION — called after every
    start_game/advance_phase/guess_location (manual or timer-fired), so it's
    idempotent and safe regardless of call ordering.
    """
    night_timer_manager.cancel(room_code)

    snapshot = await game_session_manager.get_phase_snapshot(room_code)
    if snapshot is None or snapshot.get("phase") != SpyfallPhase.DISCUSSION.value:
        return

    async def _on_timer_expired() -> None:
        await _auto_advance_phase(room_code, room_manager, connection_manager, game_session_manager, night_timer_manager)

    night_timer_manager.schedule(room_code, _on_timer_expired)
    await connection_manager.broadcast(
        room_code, DiscussionTimerStartedEvent(duration_seconds=night_timer_manager.duration_seconds)
    )


async def _auto_advance_phase(
    room_code: str,
    room_manager: RoomManager,
    connection_manager: ConnectionManager,
    game_session_manager: GameSessionManager,
    night_timer_manager: NightTimerManager,
) -> None:
    """Timer-fired equivalent of a host clicking "Advance phase" — moves
    discussion into voting once the decision window runs out."""
    room = await room_manager.get_room(room_code)
    if room is None:
        return

    try:
        events = await game_session_manager.advance_phase(room_code, room.host_player_id)
    except (PermissionDeniedError, GameNotStartedError, InvalidGameStateError, RoomNotFoundError):
        # The room may have moved on already (e.g. the host manually
        # advanced right as the timer fired) — a stale timer is a no-op.
        return

    await _broadcast_resolution_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)
    await _sync_discussion_timer(room_code, room_manager, connection_manager, game_session_manager, night_timer_manager)


def _to_ws_role_assigned(event: EngineRoleAssignedEvent) -> RoleAssignedEvent:
    return RoleAssignedEvent(is_spy=event.is_spy, location=event.location, role=event.role)


def _to_ws_game_over(event: EngineGameOverEvent) -> GameOverEvent:
    return GameOverEvent(
        winning_side=event.winning_side,
        location=event.location,
        spy_player_ids=event.spy_player_ids,
        accused_player_id=event.accused_player_id,
        reveals=[_to_ws_reveal(reveal) for reveal in event.reveals],
    )


def _to_ws_reveal(reveal: EnginePlayerRoleReveal) -> PlayerRoleRevealOut:
    return PlayerRoleRevealOut(player_id=reveal.player_id, is_spy=reveal.is_spy, role=reveal.role)


async def _send_error(
    connection_manager: ConnectionManager,
    room_code: str,
    player_id: str,
    code: str,
    message: str,
) -> None:
    await connection_manager.send_to_player(room_code, player_id, ErrorEvent(code=code, message=message))
