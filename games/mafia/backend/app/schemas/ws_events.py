from typing import Literal

from pydantic import BaseModel

from app.schemas.room import RoomOut

# ---- Server -> Client ----
# One class per event `type`. New event types get added here as later steps
# (lobby, gameplay, chat) introduce them — the dispatcher/connection manager
# don't need to change.


class RoomStateEvent(BaseModel):
    """Full room snapshot, sent once right after a socket connects."""

    type: Literal["room_state"] = "room_state"
    room: RoomOut


class PlayerConnectionChangedEvent(BaseModel):
    type: Literal["player_connection_changed"] = "player_connection_changed"
    player_id: str
    connected: bool


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str


class PongEvent(BaseModel):
    type: Literal["pong"] = "pong"


# ---- Client -> Server ----
# Parsed by hand in the dispatcher (looking at the raw `type` field) rather
# than a discriminated union, since there's only one command so far —
# lobby/game/chat commands join this list in later steps.


class PingCommand(BaseModel):
    type: Literal["ping"] = "ping"
