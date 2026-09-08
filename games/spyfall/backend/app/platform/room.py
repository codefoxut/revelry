from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class RoomPhase(str, Enum):
    """Coarse room lifecycle — distinct from a game's own internal phases
    (e.g. Mafia's Night/Day), which live inside that game's engine.
    """

    LOBBY = "lobby"
    IN_GAME = "in_game"
    FINISHED = "finished"


@dataclass
class Player:
    id: str
    display_name: str
    avatar: str
    is_host: bool = False
    is_ready: bool = False
    is_spectator: bool = False
    connected: bool = True


@dataclass
class Room:
    code: str
    game_type: str
    host_player_id: str
    is_private: bool = False
    max_players: int = 20
    phase: RoomPhase = RoomPhase.LOBBY
    players: dict[str, Player] = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def active_player_count(self) -> int:
        return sum(1 for player in self.players.values() if not player.is_spectator)
