from dataclasses import dataclass
from typing import Any, Callable

from app.game_engine.base import GameEngine

EngineFactory = Callable[..., GameEngine]


@dataclass
class GameModule:
    """Describes one pluggable game (Mafia, Codenames, ...) for the platform.

    Concrete games construct one of these and register it so the platform
    layer (room creation, lobby config) never needs game-specific knowledge.
    """

    key: str
    display_name: str
    engine_factory: EngineFactory
    min_players: int
    max_players: int
    default_config: dict[str, Any]


class GameRegistry:
    """Registry of available games, keyed by game type."""

    def __init__(self) -> None:
        self._modules: dict[str, GameModule] = {}

    def register(self, module: GameModule) -> None:
        self._modules[module.key] = module

    def get(self, key: str) -> GameModule | None:
        return self._modules.get(key)

    def list(self) -> list[GameModule]:
        return list(self._modules.values())


game_registry = GameRegistry()
