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
    phase: str
    round_number: int
    total_questions: int = 0
    option_a: str | None = None
    option_b: str | None = None
    voted: list[str] = []
    revealed_votes: dict[str, str] | None = None
    recap: list[dict] | None = None


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
