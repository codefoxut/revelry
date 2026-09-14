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


class QuestionShownEvent(BaseModel):
    """A new round's prompt is now visible; board answers are still hidden."""

    type: Literal["question_shown"] = "question_shown"
    round_number: int
    total_rounds: int
    prompt: str
    answer_count: int


class PlayerBuzzedEvent(BaseModel):
    """A team member locked in the buzzer and takes control."""

    type: Literal["player_buzzed"] = "player_buzzed"
    player_id: str
    team: str


class SlotRevealedEvent(BaseModel):
    """A board slot was guessed correctly and is now shown to everyone."""

    type: Literal["slot_revealed"] = "slot_revealed"
    slot_index: int
    text: str
    points: int


class StrikeEvent(BaseModel):
    """The controlling team got a wrong answer."""

    type: Literal["strike"] = "strike"
    team: str
    strikes: int


class StealPhaseEvent(BaseModel):
    """Three strikes have been accumulated; the other team gets one steal guess."""

    type: Literal["steal_phase"] = "steal_phase"
    stealing_team: str


class RoundOverEvent(BaseModel):
    """A round ended; `team_awarded` is None only if no slots were revealed."""

    type: Literal["round_over"] = "round_over"
    team_awarded: str | None
    points: int
    board: list[dict]


class GameOverEvent(BaseModel):
    """Final round resolved. `winning_team` is None on a tie."""

    type: Literal["game_over"] = "game_over"
    team_scores: dict[str, int]
    winning_team: str | None = None


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


class JoinTeamCommand(BaseModel):
    """A player picks which team to be on (lobby only)."""

    type: Literal["join_team"] = "join_team"
    team: Literal["a", "b"]


class StartGameCommand(BaseModel):
    """Host-only: starts the game once both teams have at least one member."""

    type: Literal["start_game"] = "start_game"


class BuzzInCommand(BaseModel):
    """A team member races to buzz in during question_open."""

    type: Literal["buzz_in"] = "buzz_in"


class RevealSlotCommand(BaseModel):
    """Host-only: marks a board slot as correctly guessed during answering."""

    type: Literal["reveal_slot"] = "reveal_slot"
    slot_index: int


class StrikeCommand(BaseModel):
    """Host-only: adds one strike to the controlling team during answering."""

    type: Literal["strike"] = "strike"


class StealRevealCommand(BaseModel):
    """Host-only: marks a slot as the stealing team's steal guess (success)."""

    type: Literal["steal_reveal"] = "steal_reveal"
    slot_index: int


class StealMissCommand(BaseModel):
    """Host-only: the stealing team's guess was wrong (steal fails)."""

    type: Literal["steal_miss"] = "steal_miss"


class NextRoundCommand(BaseModel):
    """Host-only: advances to the next round (or ends the game)."""

    type: Literal["next_round"] = "next_round"
