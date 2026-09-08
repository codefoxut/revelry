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


class QuestionShownEvent(BaseModel):
    """Public: a new question is now open for buzzing."""

    type: Literal["question_shown"] = "question_shown"
    question_number: int
    total_questions: int
    category: str
    question: str


class PlayerBuzzedEvent(BaseModel):
    """Public: a contestant locked in the buzzer, everyone else is locked out
    until the host judges their answer."""

    type: Literal["player_buzzed"] = "player_buzzed"
    player_id: str


class AnswerJudgedEvent(BaseModel):
    """Public: the host judged the buzzed-in player's spoken answer."""

    type: Literal["answer_judged"] = "answer_judged"
    player_id: str
    correct: bool
    score_delta: int


class AnswerRevealedEvent(BaseModel):
    """Public: the correct answer to the current question is now visible."""

    type: Literal["answer_revealed"] = "answer_revealed"
    answer: str


class GameOverEvent(BaseModel):
    """The final question has been answered/revealed. `winner_id` is null
    on a tie for the top score."""

    type: Literal["game_over"] = "game_over"
    scores: dict[str, int]
    winner_id: str | None = None


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
    """Host-only: moves the room out of the lobby, picks a fresh set of
    questions, and opens buzzing on the first one."""

    type: Literal["start_game"] = "start_game"


class BuzzInCommand(BaseModel):
    """A contestant racing to answer the current question out loud."""

    type: Literal["buzz_in"] = "buzz_in"


class JudgeAnswerCommand(BaseModel):
    """Host-only: judges the buzzed-in player's spoken answer."""

    type: Literal["judge_answer"] = "judge_answer"
    correct: bool


class RevealCommand(BaseModel):
    """Host-only: reveals the current answer without anyone getting it
    right, e.g. to skip a question everyone's locked out of."""

    type: Literal["reveal"] = "reveal"


class NextQuestionCommand(BaseModel):
    """Host-only: advances from the revealed answer to the next question,
    or ends the game after the last one."""

    type: Literal["next_question"] = "next_question"
