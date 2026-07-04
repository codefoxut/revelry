from __future__ import annotations

from app.game_engine.base import Event
from app.games.mafia import DISPLAY_NAME, MIN_PLAYERS
from app.games.mafia.commands import (
    AdvancePhaseCommand,
    CastVoteCommand,
    StartGameCommand,
    SubmitNightActionCommand,
)
from app.platform.exceptions import (
    GameAlreadyStartedError,
    GameNotStartedError,
    NotEnoughPlayersError,
    PermissionDeniedError,
)
from app.games.mafia.engine import MafiaGameEngine
from app.games.mafia.roles import Role
from app.platform.room import Room, RoomPhase
from app.platform.room_manager import RoomManager
from app.platform.stores.game_engine_store import GameEngineStore


class GameSessionManager:
    """Owns starting/advancing a room's game — the bridge between RoomManager
    (room lifecycle) and MafiaGameEngine (phase/rules). Mafia-specific: this
    project's games are standalone deployments, not a shared multi-game
    platform, so there's no benefit to a generic game lookup here.
    """

    def __init__(
        self,
        room_manager: RoomManager,
        engine_store: GameEngineStore,
    ) -> None:
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
                f"{DISPLAY_NAME} needs at least {MIN_PLAYERS} players "
                f"(has {room.active_player_count})"
            )

        active_player_ids = [player.id for player in room.players.values() if not player.is_spectator]

        engine = MafiaGameEngine(room_code)
        events = await engine.handle_command(
            StartGameCommand(player_id=requester_id, active_player_ids=active_player_ids)
        )
        await self._engine_store.save(room_code, engine)

        room = await self._room_manager.set_phase(room_code, RoomPhase.IN_GAME)
        return room, events

    async def advance_phase(self, room_code: str, requester_id: str) -> list[Event]:
        room = await self._room_manager.require_room(room_code)
        if room.host_player_id != requester_id:
            raise PermissionDeniedError("Only the host can advance the game's phase")

        engine = await self._engine_store.get(room_code)
        if engine is None:
            raise GameNotStartedError(f"Room {room_code!r} hasn't started a game")

        return await engine.handle_command(AdvancePhaseCommand(player_id=requester_id))

    async def submit_night_action(self, room_code: str, player_id: str, target_player_id: str) -> list[Event]:
        engine = await self._engine_store.get(room_code)
        if engine is None:
            raise GameNotStartedError(f"Room {room_code!r} hasn't started a game")

        return await engine.handle_command(
            SubmitNightActionCommand(player_id=player_id, target_player_id=target_player_id)
        )

    async def cast_vote(self, room_code: str, player_id: str, target_player_id: str) -> list[Event]:
        engine = await self._engine_store.get(room_code)
        if engine is None:
            raise GameNotStartedError(f"Room {room_code!r} hasn't started a game")

        return await engine.handle_command(CastVoteCommand(player_id=player_id, target_player_id=target_player_id))

    async def get_phase_snapshot(self, room_code: str) -> dict[str, object] | None:
        engine = await self._engine_store.get(room_code)
        return None if engine is None else engine.phase_snapshot()

    async def get_role(self, room_code: str, player_id: str) -> Role | None:
        """Pragmatic Mafia-specific accessor: "what role does this player
        have" doesn't generalize across arbitrary future games the way
        phase_snapshot does, so this reaches into MafiaGameEngine directly
        rather than adding a speculative generic method to GameEngine. Worth
        revisiting once a second game needs an equivalent concept.
        """
        engine = await self._engine_store.get(room_code)
        if not isinstance(engine, MafiaGameEngine):
            return None
        return engine.role_for(player_id)


from app.platform.room_manager import room_manager
from app.platform.stores.in_memory import InMemoryStore

game_session_manager = GameSessionManager(room_manager, GameEngineStore(InMemoryStore()))
