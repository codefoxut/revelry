from __future__ import annotations

from app.games.family_feud.events import GameOverEvent as EngineGameOverEvent
from app.games.family_feud.events import PlayerBuzzedEvent as EnginePlayerBuzzedEvent
from app.games.family_feud.events import QuestionShownEvent as EngineQuestionShownEvent
from app.games.family_feud.events import RoundOverEvent as EngineRoundOverEvent
from app.games.family_feud.events import SlotRevealedEvent as EngineSlotRevealedEvent
from app.games.family_feud.events import StealPhaseEvent as EngineStealPhaseEvent
from app.games.family_feud.events import StrikeEvent as EngineStrikeEvent
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
from app.schemas.ws_events import (
    ErrorEvent,
    GameOverEvent,
    KickedEvent,
    PlayerBuzzedEvent,
    PongEvent,
    QuestionShownEvent,
    RoundOverEvent,
    SlotRevealedEvent,
    StealPhaseEvent,
    StrikeEvent,
)
from app.services.room_presenter import broadcast_room_state
from app.websocket.connection_manager import ConnectionManager

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

    Returns True when the caller's WS receive loop should stop and close the
    socket itself (a voluntary leave).
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

    if event_type == "join_team":
        await _handle_join_team(raw_event, room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "start_game":
        await _handle_start_game(room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "buzz_in":
        await _handle_buzz_in(room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "reveal_slot":
        await _handle_reveal_slot(raw_event, room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "strike":
        await _handle_strike(room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "steal_reveal":
        await _handle_steal_reveal(raw_event, room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "steal_miss":
        await _handle_steal_miss(room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "next_round":
        await _handle_next_round(room_code, player_id, room_manager, game_session_manager, connection_manager)
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


async def _handle_join_team(
    raw_event: dict,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    team = raw_event.get("team")
    if team not in ("a", "b"):
        await _send_error(connection_manager, room_code, player_id, "invalid_payload", "`team` must be 'a' or 'b'")
        return
    try:
        await game_session_manager.join_team(room_code, player_id, team)
    except (PermissionDeniedError, GameAlreadyStartedError) as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
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
    await _broadcast_engine_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_buzz_in(
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    try:
        events = await game_session_manager.buzz_in(room_code, player_id)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except (PermissionDeniedError, InvalidGameStateError) as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return
    await _broadcast_engine_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_reveal_slot(
    raw_event: dict,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    slot_index = raw_event.get("slot_index")
    if not isinstance(slot_index, int):
        await _send_error(connection_manager, room_code, player_id, "invalid_payload", "`slot_index` must be an integer")
        return
    try:
        events = await game_session_manager.reveal_slot(room_code, player_id, slot_index)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return
    await _broadcast_engine_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_strike(
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    try:
        events = await game_session_manager.strike(room_code, player_id)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return
    await _broadcast_engine_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_steal_reveal(
    raw_event: dict,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    slot_index = raw_event.get("slot_index")
    if not isinstance(slot_index, int):
        await _send_error(connection_manager, room_code, player_id, "invalid_payload", "`slot_index` must be an integer")
        return
    try:
        events = await game_session_manager.steal_reveal(room_code, player_id, slot_index)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return
    await _broadcast_engine_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_steal_miss(
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    try:
        events = await game_session_manager.steal_miss(room_code, player_id)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return
    await _broadcast_engine_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_next_round(
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    try:
        events = await game_session_manager.next_round(room_code, player_id)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return
    await _broadcast_engine_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _broadcast_engine_events(events: list, room_code: str, connection_manager: ConnectionManager) -> None:
    for event in events:
        if isinstance(event, EngineQuestionShownEvent):
            await connection_manager.broadcast(
                room_code,
                QuestionShownEvent(
                    round_number=event.round_number,
                    total_rounds=event.total_rounds,
                    prompt=event.prompt,
                    answer_count=event.answer_count,
                ),
            )
        elif isinstance(event, EnginePlayerBuzzedEvent):
            await connection_manager.broadcast(
                room_code,
                PlayerBuzzedEvent(player_id=event.player_id, team=event.team),
            )
        elif isinstance(event, EngineSlotRevealedEvent):
            await connection_manager.broadcast(
                room_code,
                SlotRevealedEvent(slot_index=event.slot_index, text=event.text, points=event.points),
            )
        elif isinstance(event, EngineStrikeEvent):
            await connection_manager.broadcast(
                room_code,
                StrikeEvent(team=event.team, strikes=event.strikes),
            )
        elif isinstance(event, EngineStealPhaseEvent):
            await connection_manager.broadcast(
                room_code,
                StealPhaseEvent(stealing_team=event.stealing_team),
            )
        elif isinstance(event, EngineRoundOverEvent):
            await connection_manager.broadcast(
                room_code,
                RoundOverEvent(
                    team_awarded=event.team_awarded,
                    points=event.points,
                    board=event.board,
                ),
            )
        elif isinstance(event, EngineGameOverEvent):
            await connection_manager.broadcast(
                room_code,
                GameOverEvent(team_scores=event.team_scores, winning_team=event.winning_team),
            )


async def _send_error(
    connection_manager: ConnectionManager,
    room_code: str,
    player_id: str,
    code: str,
    message: str,
) -> None:
    await connection_manager.send_to_player(room_code, player_id, ErrorEvent(code=code, message=message))
