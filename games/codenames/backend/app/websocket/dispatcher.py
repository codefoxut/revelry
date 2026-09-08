from __future__ import annotations

from app.games.codenames.events import CardRevealedEvent as EngineCardRevealedEvent
from app.games.codenames.events import ClueGivenEvent as EngineClueGivenEvent
from app.games.codenames.events import GameOverEvent as EngineGameOverEvent
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
    CardRevealedEvent,
    ClueGivenEvent,
    ErrorEvent,
    GameOverEvent,
    KickedEvent,
    PongEvent,
    SpymasterViewEvent,
    TeamAssignedEvent,
)
from app.services.room_presenter import broadcast_room_state
from app.websocket.connection_manager import ConnectionManager

# Close code used when a host kicks another player from the room.
_CLOSE_KICKED = 4403

_MIN_CLUE_NUMBER = 0
_MAX_CLUE_NUMBER = 9


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
        await _handle_start_game(room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "give_clue":
        await _handle_give_clue(raw_event, room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "make_guess":
        await _handle_make_guess(raw_event, room_code, player_id, room_manager, game_session_manager, connection_manager)
        return False

    if event_type == "end_turn":
        await _handle_end_turn(room_code, player_id, room_manager, game_session_manager, connection_manager)
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
        await send_private_assignment(room_code, event.player_id, game_session_manager, connection_manager)

    await broadcast_room_state(room_code, room_manager, connection_manager, game_session_manager)


async def _handle_give_clue(
    raw_event: dict,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    word = raw_event.get("word")
    number = raw_event.get("number")
    if not isinstance(word, str) or not word.strip():
        await _send_error(connection_manager, room_code, player_id, "invalid_payload", "`word` is required")
        return
    if not isinstance(number, int) or isinstance(number, bool) or not (_MIN_CLUE_NUMBER <= number <= _MAX_CLUE_NUMBER):
        await _send_error(
            connection_manager,
            room_code,
            player_id,
            "invalid_payload",
            f"`number` must be an integer between {_MIN_CLUE_NUMBER} and {_MAX_CLUE_NUMBER}",
        )
        return

    try:
        events = await game_session_manager.give_clue(room_code, player_id, word, number)
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


async def _handle_make_guess(
    raw_event: dict,
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    card_index = raw_event.get("card_index")
    if not isinstance(card_index, int) or isinstance(card_index, bool):
        await _send_error(connection_manager, room_code, player_id, "invalid_payload", "`card_index` must be an integer")
        return

    try:
        events = await game_session_manager.make_guess(room_code, player_id, card_index)
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


async def _handle_end_turn(
    room_code: str,
    player_id: str,
    room_manager: RoomManager,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    try:
        events = await game_session_manager.end_turn(room_code, player_id)
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
        if isinstance(event, EngineClueGivenEvent):
            await connection_manager.broadcast(
                room_code, ClueGivenEvent(team=event.team.value, word=event.word, number=event.number)
            )
        elif isinstance(event, EngineCardRevealedEvent):
            await connection_manager.broadcast(
                room_code,
                CardRevealedEvent(
                    card_index=event.card_index,
                    word=event.word,
                    color=event.color.value,
                    guessed_by=event.guessed_by,
                ),
            )
        elif isinstance(event, EngineGameOverEvent):
            await connection_manager.broadcast(
                room_code,
                GameOverEvent(
                    winning_side=event.winning_side.value,
                    reason=event.reason,
                    colors=[color.value for color in event.colors],
                ),
            )


async def send_private_assignment(
    room_code: str,
    player_id: str,
    game_session_manager: GameSessionManager,
    connection_manager: ConnectionManager,
) -> None:
    """Resends a player's team/role (and, for spymasters, the full board
    colors) — used both right after start_game and on reconnect, since a
    fresh socket has no memory of what it was told before."""
    assignment = await game_session_manager.get_team_assignment(room_code, player_id)
    if assignment is None:
        return
    team, role = assignment
    await connection_manager.send_to_player(
        room_code, player_id, TeamAssignedEvent(team=team.value, role=role.value)
    )

    colors = await game_session_manager.get_spymaster_colors(room_code, player_id)
    if colors is not None:
        await connection_manager.send_to_player(room_code, player_id, SpymasterViewEvent(colors=colors))


async def _send_error(
    connection_manager: ConnectionManager,
    room_code: str,
    player_id: str,
    code: str,
    message: str,
) -> None:
    await connection_manager.send_to_player(room_code, player_id, ErrorEvent(code=code, message=message))
