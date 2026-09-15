from __future__ import annotations

from app.game_engine.base import Event
from app.games.would_you_rather import MIN_PLAYERS
from app.games.would_you_rather.commands import (
    NextQuestionCommand,
    RevealCommand,
    StartGameCommand,
    SubmitVoteCommand,
)
from app.games.would_you_rather.engine import WouldYouRatherEngine
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
    """Bridges RoomManager and the per-room WouldYouRatherEngine."""

    def __init__(self, room_manager: RoomManager, engine_store: GameEngineStore) -> None:
        self._room_manager = room_manager
        self._engine_store = engine_store

    async def start_game(self, room_code: str, requester_id: str) -> tuple[Room, list[Event]]:
        room = await self._room_manager.require_room(room_code)
        if room.host_player_id != requester_id:
            raise PermissionDeniedError("Only the host can start the game")
        if room.phase != RoomPhase.LOBBY:
            raise GameAlreadyStartedError("The game has already started")
        if room.active_player_count < MIN_PLAYERS:
            raise NotEnoughPlayersError(f"Needs at least {MIN_PLAYERS} players")

        active_player_ids = [p.id for p in room.players.values() if not p.is_spectator]

        engine = WouldYouRatherEngine(room_code)
        events = await engine.handle_command(
            StartGameCommand(player_id=requester_id, active_player_ids=active_player_ids)
        )
        await self._engine_store.save(room_code, engine)
        room = await self._room_manager.set_phase(room_code, RoomPhase.IN_GAME)
        return room, events

    async def submit_vote(self, room_code: str, player_id: str, choice: str) -> list[Event]:
        engine = await self._require_engine(room_code)
        return await engine.handle_command(SubmitVoteCommand(player_id=player_id, choice=choice))  # type: ignore[arg-type]

    async def reveal(self, room_code: str, requester_id: str) -> list[Event]:
        await self._require_host(room_code, requester_id, "reveal the votes")
        engine = await self._require_engine(room_code)
        return await engine.handle_command(RevealCommand(player_id=requester_id))

    async def next_question(self, room_code: str, requester_id: str) -> list[Event]:
        await self._require_host(room_code, requester_id, "advance to the next question")
        engine = await self._require_engine(room_code)
        return await engine.handle_command(NextQuestionCommand(player_id=requester_id))

    async def get_phase_snapshot(self, room_code: str) -> dict[str, object] | None:
        engine = await self._engine_store.get(room_code)
        return None if engine is None else engine.phase_snapshot()

    async def _require_host(self, room_code: str, requester_id: str, action: str) -> None:
        room = await self._room_manager.require_room(room_code)
        if room.host_player_id != requester_id:
            raise PermissionDeniedError(f"Only the host can {action}")

    async def _require_engine(self, room_code: str) -> WouldYouRatherEngine:
        engine = await self._engine_store.get(room_code)
        if engine is None:
            raise GameNotStartedError("The game hasn't started yet")
        assert isinstance(engine, WouldYouRatherEngine)
        return engine


game_session_manager = GameSessionManager(room_manager, GameEngineStore(InMemoryStore()))
