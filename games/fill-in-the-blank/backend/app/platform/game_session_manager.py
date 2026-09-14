from __future__ import annotations

from app.game_engine.base import Event
from app.games.fill_in_the_blank import MIN_PLAYERS
from app.games.fill_in_the_blank.commands import (
    CastVoteCommand,
    NextPromptCommand,
    RevealCommand,
    StartGameCommand,
    StartVoteCommand,
    SubmitAnswerCommand,
)
from app.games.fill_in_the_blank.engine import FillInTheBlankGameEngine
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
    """Bridges RoomManager (lobby/players) and the per-room FillInTheBlankGameEngine.

    Host-only actions (reveal/start_vote/next_prompt) are permission-checked here
    against Room.host_player_id. All players (including the host) participate.
    """

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

        active_player_ids = [
            player.id
            for player in room.players.values()
            if not player.is_spectator
        ]

        engine = FillInTheBlankGameEngine(room_code)
        events = await engine.handle_command(
            StartGameCommand(player_id=requester_id, active_player_ids=active_player_ids)
        )
        await self._engine_store.save(room_code, engine)
        room = await self._room_manager.set_phase(room_code, RoomPhase.IN_GAME)
        return room, events

    async def submit_answer(self, room_code: str, player_id: str, text: str) -> list[Event]:
        engine = await self._require_engine(room_code)
        return await engine.handle_command(SubmitAnswerCommand(player_id=player_id, text=text))

    async def reveal(self, room_code: str, requester_id: str) -> list[Event]:
        await self._require_host(room_code, requester_id, "reveal submissions")
        engine = await self._require_engine(room_code)
        return await engine.handle_command(RevealCommand(player_id=requester_id))

    async def start_vote(self, room_code: str, requester_id: str) -> list[Event]:
        await self._require_host(room_code, requester_id, "start voting")
        engine = await self._require_engine(room_code)
        return await engine.handle_command(StartVoteCommand(player_id=requester_id))

    async def cast_vote(self, room_code: str, player_id: str, submission_id: str) -> list[Event]:
        engine = await self._require_engine(room_code)
        return await engine.handle_command(CastVoteCommand(player_id=player_id, submission_id=submission_id))

    async def next_prompt(self, room_code: str, requester_id: str) -> list[Event]:
        await self._require_host(room_code, requester_id, "advance to the next prompt")
        engine = await self._require_engine(room_code)
        return await engine.handle_command(NextPromptCommand(player_id=requester_id))

    async def get_phase_snapshot(self, room_code: str) -> dict[str, object] | None:
        engine = await self._engine_store.get(room_code)
        return None if engine is None else engine.phase_snapshot()

    async def _require_host(self, room_code: str, requester_id: str, action: str) -> None:
        room = await self._room_manager.require_room(room_code)
        if room.host_player_id != requester_id:
            raise PermissionDeniedError(f"Only the host can {action}")

    async def _require_engine(self, room_code: str) -> FillInTheBlankGameEngine:
        engine = await self._engine_store.get(room_code)
        if engine is None:
            raise GameNotStartedError("The game hasn't started yet")
        assert isinstance(engine, FillInTheBlankGameEngine)
        return engine


game_session_manager = GameSessionManager(room_manager, GameEngineStore(InMemoryStore()))
