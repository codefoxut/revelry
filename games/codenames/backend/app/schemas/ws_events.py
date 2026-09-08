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


class TeamAssignedEvent(BaseModel):
    """A player's own team + role, sent only to that player (once at game
    start, and again on reconnect) — never broadcast to the room.
    """

    type: Literal["team_assigned"] = "team_assigned"
    team: str
    role: str


class SpymasterViewEvent(BaseModel):
    """The full 25-card color list, sent only to that room's two spymasters
    (once at game start, and again on reconnect) — never broadcast, since
    it's the one piece of state guessers must never see.
    """

    type: Literal["spymaster_view"] = "spymaster_view"
    colors: list[str]


class ClueGivenEvent(BaseModel):
    """Public: the active team's spymaster has given a clue."""

    type: Literal["clue_given"] = "clue_given"
    team: str
    word: str
    number: int


class CardRevealedEvent(BaseModel):
    """Public: a card has been guessed and its color revealed."""

    type: Literal["card_revealed"] = "card_revealed"
    card_index: int
    word: str
    color: str
    guessed_by: str


class GameOverEvent(BaseModel):
    """The game has ended, either by a team finding all their words or by
    someone guessing the assassin card. `colors` is the full board, now
    safe to reveal to everyone.
    """

    type: Literal["game_over"] = "game_over"
    winning_side: str
    reason: str
    colors: list[str]


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
    """Host-only: moves the room out of the lobby, randomly assigning teams
    and spymasters and dealing a fresh 25-word board."""

    type: Literal["start_game"] = "start_game"


class GiveClueCommand(BaseModel):
    """The active team's spymaster's clue for this turn."""

    type: Literal["give_clue"] = "give_clue"
    word: str
    number: int


class MakeGuessCommand(BaseModel):
    """A guesser on the active team guessing one unrevealed card."""

    type: Literal["make_guess"] = "make_guess"
    card_index: int


class EndTurnCommand(BaseModel):
    """A guesser on the active team voluntarily passing the turn."""

    type: Literal["end_turn"] = "end_turn"
