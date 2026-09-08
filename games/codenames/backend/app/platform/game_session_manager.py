from __future__ import annotations

from app.game_engine.base import Event
from app.games.codenames import DISPLAY_NAME, MIN_PLAYERS
from app.games.codenames.board import Role, Team
from app.games.codenames.commands import EndTurnCommand, GiveClueCommand, MakeGuessCommand, StartGameCommand
from app.games.codenames.engine import CodenamesGameEngine
from app.platform.exceptions import (
    GameAlreadyStartedError,
    GameNotStartedError,
    NotEnoughPlayersError,
    PermissionDeniedError,
)
from app.platform.room import Room, RoomPhase
from app.platform.room_manager import RoomManager, room_manager
from app.platform.stores.game_engine_store import GameEngineStore
from app.platform.stores.in_memory import InMemoryStore


class GameSessionManager:
    """Owns starting/advancing a room's game — the bridge between RoomManager
    (room lifecycle) and CodenamesGameEngine (phase/rules). Codenames-specific:
    this project's games are standalone deployments, not a shared
    multi-game platform, so there's no benefit to a generic game lookup here.
    """

    def __init__(self, room_manager: RoomManager, engine_store: GameEngineStore) -> None:
        self._room_manager = room_manager
        self._engine_store = engine_store

    async def start_game(self, room_code: str, requester_id: str) -> tuple[Room, list[Event]]:
        room = await self._room_manager.require_room(room_code)
        if room.host_player_id != requester_id:
            raise PermissionDeniedError("Only the host can start the game")
        if room.phase != RoomPhase.LOBBY:
            raise GameAlreadyStartedError(f"Room {room_code!r} has already started")

        if room.active_player_count < MIN_PLAYERS:
            raise NotEnoughPlayersError(
                f"{DISPLAY_NAME} needs at least {MIN_PLAYERS} players (has {room.active_player_count})"
            )

        active_player_ids = [player.id for player in room.players.values() if not player.is_spectator]

        engine = CodenamesGameEngine(room_code)
        events = await engine.handle_command(
            StartGameCommand(player_id=requester_id, active_player_ids=active_player_ids)
        )
        await self._engine_store.save(room_code, engine)

        room = await self._room_manager.set_phase(room_code, RoomPhase.IN_GAME)
        return room, events

    async def give_clue(self, room_code: str, player_id: str, word: str, number: int) -> list[Event]:
        engine = await self._require_engine(room_code)
        return await engine.handle_command(GiveClueCommand(player_id=player_id, word=word, number=number))

    async def make_guess(self, room_code: str, player_id: str, card_index: int) -> list[Event]:
        engine = await self._require_engine(room_code)
        return await engine.handle_command(MakeGuessCommand(player_id=player_id, card_index=card_index))

    async def end_turn(self, room_code: str, player_id: str) -> list[Event]:
        engine = await self._require_engine(room_code)
        return await engine.handle_command(EndTurnCommand(player_id=player_id))

    async def get_phase_snapshot(self, room_code: str) -> dict[str, object] | None:
        engine = await self._engine_store.get(room_code)
        return None if engine is None else engine.phase_snapshot()

    async def get_team_assignment(self, room_code: str, player_id: str) -> tuple[Team, Role] | None:
        engine = await self._engine_store.get(room_code)
        if not isinstance(engine, CodenamesGameEngine):
            return None
        return engine.get_team_assignment(player_id)

    async def get_spymaster_colors(self, room_code: str, player_id: str) -> list[str] | None:
        engine = await self._engine_store.get(room_code)
        if not isinstance(engine, CodenamesGameEngine):
            return None
        return engine.get_spymaster_colors(player_id)

    async def _require_engine(self, room_code: str) -> CodenamesGameEngine:
        engine = await self._engine_store.get(room_code)
        if engine is None:
            raise GameNotStartedError(f"Room {room_code!r} hasn't started a game")
        return engine


game_session_manager = GameSessionManager(room_manager, GameEngineStore(InMemoryStore()))
