from __future__ import annotations

from app.schemas.ws_events import ErrorEvent, PongEvent
from app.websocket.connection_manager import ConnectionManager


async def dispatch_client_event(
    raw_event: dict,
    *,
    room_code: str,
    player_id: str,
    connection_manager: ConnectionManager,
) -> None:
    """Route one parsed client message to its handler.

    This grows a branch per command as later steps add lobby actions, game
    commands, and chat — kept as a plain dispatch table rather than a class
    since there's no shared state beyond what's passed in.
    """
    event_type = raw_event.get("type")

    if event_type == "ping":
        await connection_manager.send_to_player(room_code, player_id, PongEvent())
        return

    await connection_manager.send_to_player(
        room_code,
        player_id,
        ErrorEvent(code="unknown_event", message=f"Unrecognized event type: {event_type!r}"),
    )
