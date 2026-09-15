from __future__ import annotations

from app.game_engine.base import Event
from app.games.wavelength import DISPLAY_NAME, MIN_PLAYERS
from app.games.wavelength.commands import (
    GiveClueCommand,
    NextRoundCommand,
    RevealCommand,
    StartGameCommand,
    SubmitGuessCommand,
)
from app.games.wavelength.engine import WavelengthEngine
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
        engine = WavelengthEngine(room_code)
        events = await engine.handle_command(
            StartGameCommand(player_id=requester_id, active_player_ids=active_player_ids)
        )
        await self._engine_store.save(room_code, engine)

        room = await self._room_manager.set_phase(room_code, RoomPhase.IN_GAME)
        return room, events

    async def give_clue(self, room_code: str, player_id: str, clue_text: str) -> list[Event]:
        engine = await self._require_engine(room_code)
        return await engine.handle_command(GiveClueCommand(player_id=player_id, clue_text=clue_text))

    async def submit_guess(self, room_code: str, player_id: str, position: float) -> list[Event]:
        engine = await self._require_engine(room_code)
        return await engine.handle_command(SubmitGuessCommand(player_id=player_id, position=position))

    async def reveal(self, room_code: str, player_id: str) -> list[Event]:
        engine = await self._require_engine(room_code)
        return await engine.handle_command(RevealCommand(player_id=player_id))

    async def next_round(self, room_code: str, player_id: str) -> list[Event]:
        engine = await self._require_engine(room_code)
        return await engine.handle_command(NextRoundCommand(player_id=player_id))

    async def get_phase_snapshot(self, room_code: str) -> dict[str, object] | None:
        engine = await self._engine_store.get(room_code)
        return None if engine is None else engine.phase_snapshot()

    async def get_target_position(self, room_code: str, player_id: str) -> float | None:
        engine = await self._engine_store.get(room_code)
        if not isinstance(engine, WavelengthEngine):
            return None
        return engine.get_target_position(player_id)

    async def _require_engine(self, room_code: str) -> WavelengthEngine:
        engine = await self._engine_store.get(room_code)
        if engine is None:
            raise GameNotStartedError(f"Room {room_code!r} hasn't started a game")
        return engine  # type: ignore[return-value]


game_session_manager = GameSessionManager(room_manager, GameEngineStore(InMemoryStore()))
