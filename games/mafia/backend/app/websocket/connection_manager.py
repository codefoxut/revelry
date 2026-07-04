from __future__ import annotations

from fastapi import WebSocket
from pydantic import BaseModel


class ConnectionManager:
    """Tracks live WebSocket connections, keyed by room code then player id.

    Pure connection bookkeeping — no room or game business logic lives here,
    and no game ever imports this directly (the WS router mediates). Reusable
    as-is by future Revelry games.
    """

    def __init__(self) -> None:
        self._connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, room_code: str, player_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(room_code, {})[player_id] = websocket

    def disconnect(self, room_code: str, player_id: str) -> None:
        room_connections = self._connections.get(room_code)
        if room_connections is None:
            return
        room_connections.pop(player_id, None)
        if not room_connections:
            self._connections.pop(room_code, None)

    async def send_to_player(self, room_code: str, player_id: str, event: BaseModel) -> None:
        websocket = self._connections.get(room_code, {}).get(player_id)
        if websocket is not None:
            await websocket.send_json(event.model_dump(mode="json"))

    async def broadcast(
        self,
        room_code: str,
        event: BaseModel,
        exclude_player_id: str | None = None,
    ) -> None:
        payload = event.model_dump(mode="json")
        for player_id, websocket in list(self._connections.get(room_code, {}).items()):
            if player_id == exclude_player_id:
                continue
            await websocket.send_json(payload)
