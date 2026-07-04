from pydantic import BaseModel


class CreateRoomRequest(BaseModel):
    game_type: str
    host_display_name: str
    host_avatar: str = "default"
    is_private: bool = False


class PlayerOut(BaseModel):
    id: str
    display_name: str
    avatar: str
    is_host: bool
    is_ready: bool
    is_spectator: bool
    connected: bool


class RoomOut(BaseModel):
    code: str
    game_type: str
    is_private: bool
    phase: str
    max_players: int
    players: list[PlayerOut]
    invite_url: str


class CreateRoomResponse(BaseModel):
    room: RoomOut
    player_id: str


class RoomSummary(BaseModel):
    """Public, pre-join view of a room — no player identities, so a client
    can validate a room code before it has joined (and before a WebSocket
    connection exists).
    """

    code: str
    game_type: str
    phase: str
    is_private: bool
    player_count: int
    max_players: int
