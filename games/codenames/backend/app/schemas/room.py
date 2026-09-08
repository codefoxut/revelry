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


class BoardCardOut(BaseModel):
    """One card's public view. `color` is null until `revealed` is true —
    the board's colors are the one piece of state that's genuinely
    per-role (spymaster vs. guesser) rather than per-phase, so the full
    color list travels separately as a private event instead of living
    here.
    """

    word: str
    revealed: bool
    color: str | None


class CurrentClueOut(BaseModel):
    word: str
    number: int
    guesses_made: int
    max_guesses: int


class GameStateOut(BaseModel):
    """Where the room's active game currently is. Absent while still in the
    lobby; every phase-driven game reports at least a phase name and a
    round/turn counter (see GameEngine.phase_snapshot).
    """

    phase: str
    round_number: int
    current_team: str | None = None
    current_clue: CurrentClueOut | None = None
    board: list[BoardCardOut] = []
    red_remaining: int = 0
    blue_remaining: int = 0


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
