from typing import Literal

from pydantic import BaseModel

from app.schemas.room import RoomOut

# ---- Server -> Client ----


class RoomStateEvent(BaseModel):
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


class PsychicTargetEvent(BaseModel):
    """The target position — sent ONLY to the current Psychic's socket.
    Never broadcast. Sent at round start and on reconnect.
    """

    type: Literal["psychic_target"] = "psychic_target"
    target_position: float


class ClueGivenEvent(BaseModel):
    """Public: Psychic has given their clue (optional typed text)."""

    type: Literal["clue_given"] = "clue_given"
    clue_text: str
    psychic_id: str


class PlayerGuessedEvent(BaseModel):
    """Public: count-only update when a guesser locks in."""

    type: Literal["player_guessed"] = "player_guessed"
    player_id: str
    guessed_count: int


class RevealedEvent(BaseModel):
    """Public: target revealed + every guesser's position + round points."""

    type: Literal["revealed"] = "revealed"
    target_position: float
    guesses: dict[str, float]
    points_awarded: dict[str, int]


class GameOverEvent(BaseModel):
    """Public: game over with final scores."""

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


class GiveClueCommand(BaseModel):
    type: Literal["give_clue"] = "give_clue"
    clue_text: str = ""


class SubmitGuessCommand(BaseModel):
    type: Literal["submit_guess"] = "submit_guess"
    position: float


class RevealCommand(BaseModel):
    type: Literal["reveal"] = "reveal"


class NextRoundCommand(BaseModel):
    type: Literal["next_round"] = "next_round"
