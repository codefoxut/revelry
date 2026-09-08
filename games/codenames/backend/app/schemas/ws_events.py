from typing import Literal

from pydantic import BaseModel

from app.schemas.room import RoomOut

# ---- Server -> Client ----
# One class per event `type`. New event types get added here as later steps
# introduce them — the dispatcher/connection manager don't need to change.


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
    """A player's own assignment, sent only to that player (once at game
    start, and again on reconnect) — never broadcast to the room.
    `location`/`role` are both null exactly when `is_spy` is true.
    """

    type: Literal["role_assigned"] = "role_assigned"
    is_spy: bool
    location: str | None
    role: str | None


class VoteCastEvent(BaseModel):
    """A single public vote during VOTING. Votes are open, so this is
    broadcast to the whole room as each one comes in.
    """

    type: Literal["vote_cast"] = "vote_cast"
    player_id: str
    target_player_id: str


class PlayerRoleRevealOut(BaseModel):
    """One player's final assignment, only ever sent alongside
    `GameOverEvent` — it stops being private information once the game has
    ended."""

    player_id: str
    is_spy: bool
    role: str | None


class GameOverEvent(BaseModel):
    """The game has ended. `accused_player_id` is null when the spy won by
    correctly guessing the location, or by evading a tied/no-consensus
    vote — otherwise it's whoever the room voted to accuse.
    """

    type: Literal["game_over"] = "game_over"
    winning_side: str
    location: str
    spy_player_ids: list[str]
    accused_player_id: str | None
    reveals: list[PlayerRoleRevealOut]


class DiscussionTimerStartedEvent(BaseModel):
    """Public: a new discussion window has started, giving the room
    `duration_seconds` before it auto-advances to VOTING.
    """

    type: Literal["discussion_timer_started"] = "discussion_timer_started"
    duration_seconds: float


# ---- Client -> Server ----
# Parsed by hand in the dispatcher (looking at the raw `type` field) rather
# than a discriminated union — keeps adding a command a one-line diff in the
# dispatcher instead of touching a shared union type.


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
    """Host-only: moves the room out of the lobby into DISCUSSION.

    `enabled_location_keys` restricts which locations can be picked for
    this round; omitted or null falls back to the full location bank (see
    locations.py).
    """

    type: Literal["start_game"] = "start_game"
    enabled_location_keys: list[str] | None = None


class AdvancePhaseCommand(BaseModel):
    """Host-only: manually advances to the next phase — DISCUSSION -> VOTING,
    or VOTING -> GAME_OVER (resolving the vote). Stands in for automatic
    timer/vote-driven advancement during DISCUSSION.
    """

    type: Literal["advance_phase"] = "advance_phase"


class CastVoteCommand(BaseModel):
    """A player's public vote for who they think the spy is, cast during
    VOTING."""

    type: Literal["cast_vote"] = "cast_vote"
    target_player_id: str


class GuessLocationCommand(BaseModel):
    """The spy's alternate win condition: guessing the secret location.
    Valid at any time during DISCUSSION or VOTING.
    """

    type: Literal["guess_location"] = "guess_location"
    location_key: str
