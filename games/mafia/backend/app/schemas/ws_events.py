from typing import Literal

from pydantic import BaseModel

from app.schemas.room import RoleOut, RoomOut

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


class KickedEvent(BaseModel):
    """Sent to a player right before the server closes their socket after
    a host kick, so the client can show why it was disconnected.
    """

    type: Literal["kicked"] = "kicked"


class RoleAssignedEvent(BaseModel):
    """A player's own role, sent only to that player (once at game start,
    and again on reconnect) — never broadcast to the room.
    """

    type: Literal["role_assigned"] = "role_assigned"
    role: RoleOut


# ---- Client -> Server ----
# Parsed by hand in the dispatcher (looking at the raw `type` field) rather
# than a discriminated union — keeps adding a command a one-line diff in the
# dispatcher instead of touching a shared union type. Game/chat commands
# join this list in later steps.


class PingCommand(BaseModel):
    type: Literal["ping"] = "ping"


class SetReadyCommand(BaseModel):
    type: Literal["set_ready"] = "set_ready"
    ready: bool


class UpdateProfileCommand(BaseModel):
    type: Literal["update_profile"] = "update_profile"
    display_name: str | None = None
    avatar: str | None = None


class KickPlayerCommand(BaseModel):
    type: Literal["kick_player"] = "kick_player"
    target_player_id: str


class LeaveRoomCommand(BaseModel):
    type: Literal["leave_room"] = "leave_room"


class StartGameCommand(BaseModel):
    """Host-only: moves the room out of the lobby into the game's first
    phase (Mafia: NIGHT).
    """

    type: Literal["start_game"] = "start_game"


class AdvancePhaseCommand(BaseModel):
    """Host-only: manually advances to the next phase in the game's cycle.
    Stands in for automatic timer/vote-driven advancement (later steps).
    """

    type: Literal["advance_phase"] = "advance_phase"
