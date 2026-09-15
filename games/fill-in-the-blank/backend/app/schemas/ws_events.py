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


class PromptShownEvent(BaseModel):
    """Broadcast when a new prompt is shown — includes question number."""

    type: Literal["prompt_shown"] = "prompt_shown"
    prompt: str
    question_number: int
    total_questions: int


class PlayerSubmittedEvent(BaseModel):
    """Broadcast when a player submits (count-only — no text until reveal)."""

    type: Literal["player_submitted"] = "player_submitted"
    player_id: str


class SubmissionsRevealedEvent(BaseModel):
    """Broadcast at reveal — shuffled [{submission_id, text}], no author_id."""

    type: Literal["submissions_revealed"] = "submissions_revealed"
    submissions: list[dict]


class PlayerVotedEvent(BaseModel):
    """Broadcast when a player casts a vote (count-only, not which submission)."""

    type: Literal["player_voted"] = "player_voted"
    player_id: str


class VoteResultsEvent(BaseModel):
    """Broadcast after voting closes — includes author_id for the first time."""

    type: Literal["vote_results"] = "vote_results"
    results: list[dict]  # [{submission_id, text, author_id, votes}]


class RoundOverEvent(BaseModel):
    """Broadcast alongside VoteResultsEvent with points awarded this round."""

    type: Literal["round_over"] = "round_over"
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


class SubmitAnswerCommand(BaseModel):
    type: Literal["submit_answer"] = "submit_answer"
    text: str


class RevealCommand(BaseModel):
    """Host-only: reveal shuffled submissions after prompt_open."""

    type: Literal["reveal"] = "reveal"


class StartVoteCommand(BaseModel):
    """Host-only: open voting after submissions_revealed."""

    type: Literal["start_vote"] = "start_vote"


class CastVoteCommand(BaseModel):
    """Any player votes for a submission (server rejects self-votes)."""

    type: Literal["cast_vote"] = "cast_vote"
    submission_id: str


class NextPromptCommand(BaseModel):
    """Host-only: from voting (compute results) or results (next prompt / game over)."""

    type: Literal["next_prompt"] = "next_prompt"
