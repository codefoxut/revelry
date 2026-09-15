from pydantic import BaseModel


class CreateRoomRequest(BaseModel):
    game_type: str
    host_display_name: str
    host_avatar: str = "default"
    is_private: bool = False


class JoinRoomRequest(BaseModel):
    display_name: str
    avatar: str = "default"
    as_spectator: bool = False


class PlayerOut(BaseModel):
    id: str
    display_name: str
    avatar: str
    is_host: bool
    is_ready: bool
    is_spectator: bool
    connected: bool


class GameStateOut(BaseModel):
    """Current Wavelength game state broadcast to all players.

    target_position is only populated during the reveal phase (public by then).
    During clue_giving and guessing it is always None — target travels privately
    via PsychicTargetEvent to the Psychic's socket only.
    """

    phase: str
    round_number: int
    total_rounds: int
    psychic_id: str | None = None
    left_label: str = ""
    right_label: str = ""
    target_position: float | None = None
    clue_text: str | None = None
    guessed_count: int = 0
    guesses: dict[str, float] | None = None
    points_awarded: dict[str, int] | None = None
    scores: dict[str, int] = {}


class RoomOut(BaseModel):
    code: str
    game_type: str
    is_private: bool
    phase: str
    max_players: int
    players: list[PlayerOut]
    invite_url: str
    game_state: GameStateOut | None = None


class CreateRoomResponse(BaseModel):
    room: RoomOut
    player_id: str


class RoomSummary(BaseModel):
    code: str
    game_type: str
    phase: str
    is_private: bool
    player_count: int
    max_players: int
