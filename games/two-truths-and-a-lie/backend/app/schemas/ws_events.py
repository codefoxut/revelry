from typing import Literal

from pydantic import BaseModel

from app.schemas.room import RoomOut

# ---- Server -> Client ----


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
    type: Literal["kicked"] = "kicked"


class RoundStartedEvent(BaseModel):
    """Broadcast when a new round begins — the new Storyteller's id."""

    type: Literal["round_started"] = "round_started"
    storyteller_id: str


class StatementsSubmittedEvent(BaseModel):
    """Broadcast once the Storyteller submits — reveals the 3 statements,
    never the lie_index."""

    type: Literal["statements_submitted"] = "statements_submitted"
    statements: list[str]


class PlayerVotedEvent(BaseModel):
    """Broadcast when any player casts a vote (count-only, not the choice)."""

    type: Literal["player_voted"] = "player_voted"
    player_id: str


class RevealedEvent(BaseModel):
    """Broadcast at reveal — includes lie_index for the first time."""

    type: Literal["revealed"] = "revealed"
    lie_index: int
    correct_voters: list[str]
    scores_delta: dict[str, int]


class GameOverEvent(BaseModel):
    type: Literal["game_over"] = "game_over"
    scores: dict[str, int]


# ---- Client -> Server ----


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
    type: Literal["start_game"] = "start_game"


class SubmitStatementsCommand(BaseModel):
    """Storyteller-only: submit the 3 statements and which index is the lie."""

    type: Literal["submit_statements"] = "submit_statements"
    statements: list[str]
    lie_index: int


class CastVoteCommand(BaseModel):
    """Any non-Storyteller player votes for which statement is the lie."""

    type: Literal["cast_vote"] = "cast_vote"
    choice_index: int


class RevealCommand(BaseModel):
    """Host-only: force early reveal before all votes are in."""

    type: Literal["reveal"] = "reveal"


class NextRoundCommand(BaseModel):
    """Host-only: advance from reveal to the next round (or game over)."""

    type: Literal["next_round"] = "next_round"
