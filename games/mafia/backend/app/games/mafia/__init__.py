from app.games.mafia.engine import MafiaGameEngine
from app.platform.game_registry import GameModule, game_registry

MAFIA_MODULE = GameModule(
    key="mafia",
    display_name="Mafia",
    engine_factory=MafiaGameEngine,
    min_players=4,
    max_players=20,
    default_config={},
)

game_registry.register(MAFIA_MODULE)
