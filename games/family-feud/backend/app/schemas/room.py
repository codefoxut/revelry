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


class BoardSlotOut(BaseModel):
    text: str | None = None
    points: int | None = None
    revealed: bool = False


class GameStateOut(BaseModel):
    """Where the room's active game currently is — always present for family
    feud, even in lobby, so that team assignments are visible before game start.
    """

    phase: str
    round_number: int = 0
    total_rounds: int = 0
    prompt: str | None = None
    answer_count: int = 0
    board: list[BoardSlotOut] = []
    controlling_team: str | None = None
    strikes: int = 0
    team_scores: dict[str, int] = {}
    team_of: dict[str, str] = {}


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
