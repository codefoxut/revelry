from __future__ import annotations

from app.games.fill_in_the_blank.events import GameOverEvent as EngineGameOverEvent
from app.games.fill_in_the_blank.events import PlayerSubmittedEvent as EnginePlayerSubmittedEvent
from app.games.fill_in_the_blank.events import PlayerVotedEvent as EnginePlayerVotedEvent
from app.games.fill_in_the_blank.events import PromptShownEvent as EnginePromptShownEvent
from app.games.fill_in_the_blank.events import RoundOverEvent as EngineRoundOverEvent
from app.games.fill_in_the_blank.events import SubmissionsRevealedEvent as EngineSubmissionsRevealedEvent
from app.games.fill_in_the_blank.events import VoteResultsEvent as EngineVoteResultsEvent
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
    PlayerSubmittedEvent,
    PlayerVotedEvent,
    PongEvent,
    PromptShownEvent,
    RoundOverEvent,
    SubmissionsRevealedEvent,
    VoteResultsEvent,
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

    Returns True when the caller's WS receive loop should close the socket.
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

    if event_type == "submit_answer":
        await _handle_submit_answer(raw_event, room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "reveal":
        await _handle_reveal(room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "start_vote":
        await _handle_start_vote(room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "cast_vote":
        await _handle_cast_vote(raw_event, room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "next_prompt":
        await _handle_next_prompt(room_code, player_id, room_manager, game_session_manager, connection_manager)
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
        await _send_error(connection_manager, room_code, player_id, "invalid_payload", "At least one of `display_name` or `avatar` is required")
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
    await _broadcast_resolution_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_submit_answer(
    raw_event: dict,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    text = raw_event.get("text")
    if not isinstance(text, str) or not text.strip():
        await _send_error(connection_manager, room_code, player_id, "invalid_payload", "`text` must be a non-empty string")
        return
    try:
        events = await game_session_manager.submit_answer(room_code, player_id, text)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return
    await _broadcast_resolution_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_reveal(
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    try:
        events = await game_session_manager.reveal(room_code, player_id)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return
    await _broadcast_resolution_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_start_vote(
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    try:
        events = await game_session_manager.start_vote(room_code, player_id)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return
    await _broadcast_resolution_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_cast_vote(
    raw_event: dict,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    submission_id = raw_event.get("submission_id")
    if not isinstance(submission_id, str) or not submission_id:
        await _send_error(connection_manager, room_code, player_id, "invalid_payload", "`submission_id` must be a non-empty string")
        return
    try:
        events = await game_session_manager.cast_vote(room_code, player_id, submission_id)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return
    await _broadcast_resolution_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_next_prompt(
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    try:
        events = await game_session_manager.next_prompt(room_code, player_id)
    except GameNotStartedError as exc:
        await _send_error(connection_manager, room_code, player_id, "game_not_started", str(exc))
        return
    except PermissionDeniedError as exc:
        await _send_error(connection_manager, room_code, player_id, "permission_denied", str(exc))
        return
    except InvalidGameStateError as exc:
        await _send_error(connection_manager, room_code, player_id, "invalid_game_state", str(exc))
        return
    await _broadcast_resolution_events(events, room_code, connection_manager)
    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _broadcast_resolution_events(events: list, room_code: str, connection_manager: ConnectionManager) -> None:
    for event in events:
        if isinstance(event, EnginePromptShownEvent):
            await connection_manager.broadcast(
                room_code,
                PromptShownEvent(
                    prompt=event.prompt,
                    question_number=event.question_number,
                    total_questions=event.total_questions,
                ),
            )
        elif isinstance(event, EnginePlayerSubmittedEvent):
            await connection_manager.broadcast(room_code, PlayerSubmittedEvent(player_id=event.player_id))
        elif isinstance(event, EngineSubmissionsRevealedEvent):
            await connection_manager.broadcast(
                room_code,
                SubmissionsRevealedEvent(submissions=event.submissions),
            )
        elif isinstance(event, EnginePlayerVotedEvent):
            await connection_manager.broadcast(room_code, PlayerVotedEvent(player_id=event.player_id))
        elif isinstance(event, EngineVoteResultsEvent):
            await connection_manager.broadcast(room_code, VoteResultsEvent(results=event.results))
        elif isinstance(event, EngineRoundOverEvent):
            await connection_manager.broadcast(room_code, RoundOverEvent(scores_delta=event.scores_delta))
        elif isinstance(event, EngineGameOverEvent):
            await connection_manager.broadcast(room_code, GameOverEvent(scores=event.scores))


async def _send_error(
    connection_manager: ConnectionManager,
    room_code: str,
    player_id: str,
    code: str,
    message: str,
) -> None:
    await connection_manager.send_to_player(room_code, player_id, ErrorEvent(code=code, message=message))
