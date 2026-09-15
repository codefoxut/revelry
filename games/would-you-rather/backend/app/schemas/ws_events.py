from typing import Literal

from pydantic import BaseModel

from app.schemas.room import RoomOut


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
    type: Literal["question_shown"] = "question_shown"
    question_number: int
    total_questions: int
    option_a: str
    option_b: str


class PlayerVotedEvent(BaseModel):
    type: Literal["player_voted"] = "player_voted"
    player_id: str


class VotesRevealedEvent(BaseModel):
    type: Literal["votes_revealed"] = "votes_revealed"
    votes: dict[str, str]


class GameOverEvent(BaseModel):
    type: Literal["game_over"] = "game_over"
    recap: list[dict]
