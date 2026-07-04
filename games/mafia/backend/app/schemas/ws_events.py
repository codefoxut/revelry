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


class InvestigationResultEvent(BaseModel):
    """The detective's own investigation result — sent only to them."""

    type: Literal["investigation_result"] = "investigation_result"
    target_player_id: str
    team: str


class NightResultEvent(BaseModel):
    """Public announcement of who (if anyone) died overnight."""

    type: Literal["night_result"] = "night_result"
    eliminated_player_id: str | None


class EliminationResultEvent(BaseModel):
    """Public announcement of who (if anyone) the town voted out."""

    type: Literal["elimination_result"] = "elimination_result"
    eliminated_player_id: str | None


class GameOverEvent(BaseModel):
    type: Literal["game_over"] = "game_over"
    winning_team: str


class VoteCastEvent(BaseModel):
    """A single public vote during the day. Votes are open, so this is
    broadcast to the whole room as each one comes in.
    """

    type: Literal["vote_cast"] = "vote_cast"
    player_id: str
    target_player_id: str


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


class NightActionCommand(BaseModel):
    """A living player's night action. Meaning depends on their role; the
    engine validates phase/alive/role, not this layer.
    """

    type: Literal["night_action"] = "night_action"
    target_player_id: str


class CastVoteCommand(BaseModel):
    """A living player's public vote during VOTING."""

    type: Literal["cast_vote"] = "cast_vote"
    target_player_id: str
