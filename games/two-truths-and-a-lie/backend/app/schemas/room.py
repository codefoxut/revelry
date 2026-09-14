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
    """Where the active Two Truths and a Lie game currently is."""

    phase: str
    round_number: int
    total_rounds: int = 0
    storyteller_id: str | None = None
    statements: list[str] | None = None
    voted_count: int = 0
    # lie_index is absent from the snapshot until reveal — see engine.phase_snapshot()
    lie_index: int | None = None
    correct_voters: list[str] | None = None
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
