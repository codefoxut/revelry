from __future__ import annotations

from typing import Literal

from app.game_engine.base import Event
from app.games.family_feud.commands import (
    BuzzInCommand,
    NextRoundCommand,
    RevealSlotCommand,
    StartGameCommand,
    StealMissCommand,
    StealRevealCommand,
    StrikeCommand,
)
from app.games.family_feud.engine import FamilyFeudGameEngine
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

_MIN_PLAYERS_PER_TEAM = 1


class GameSessionManager:
    """Bridges RoomManager (lobby/players) and the per-room FamilyFeudGameEngine.

    Team assignments (join_team) are stored in Room.config["teams"] before game
    start and passed to the engine via StartGameCommand — keeping team data out of
    the shared Platform Player model as required by the game plan.

    Host-only actions are permission-checked here against Room.host_player_id.
    """

    def __init__(self, room_manager: RoomManager, engine_store: GameEngineStore) -> None:
        self._room_manager = room_manager
        self._engine_store = engine_store

    async def join_team(
        self, room_code: str, player_id: str, team: Literal["a", "b"]
    ) -> tuple[Room, list[Event]]:
        room = await self._room_manager.require_room(room_code)
        if room.phase != RoomPhase.LOBBY:
            raise GameAlreadyStartedError("Can't switch teams after the game has started")
        if player_id not in room.players:
            raise PermissionDeniedError("Player not in room")
        if room.host_player_id == player_id:
            raise PermissionDeniedError("The host doesn't play on a team")

        if "teams" not in room.config:
            room.config["teams"] = {}
        room.config["teams"][player_id] = team
        return room, []

    async def start_game(self, room_code: str, requester_id: str) -> tuple[Room, list[Event]]:
        room = await self._room_manager.require_room(room_code)
        if room.host_player_id != requester_id:
            raise PermissionDeniedError("Only the host can start the game")
        if room.phase != RoomPhase.LOBBY:
            raise GameAlreadyStartedError("The game has already started")

        teams: dict[str, Literal["a", "b"]] = room.config.get("teams", {})
        team_a = [pid for pid, t in teams.items() if t == "a" and pid in room.players]
        team_b = [pid for pid, t in teams.items() if t == "b" and pid in room.players]

        if len(team_a) < _MIN_PLAYERS_PER_TEAM or len(team_b) < _MIN_PLAYERS_PER_TEAM:
            raise NotEnoughPlayersError(
                "Both teams need at least one player — assign everyone to a team before starting"
            )

        engine = FamilyFeudGameEngine(room_code)
        events = await engine.handle_command(
            StartGameCommand(player_id=requester_id, team_of=teams)
        )
        await self._engine_store.save(room_code, engine)
        room = await self._room_manager.set_phase(room_code, RoomPhase.IN_GAME)
        return room, events

    async def buzz_in(self, room_code: str, player_id: str) -> list[Event]:
        engine = await self._require_engine(room_code)
        return await engine.handle_command(BuzzInCommand(player_id=player_id))

    async def reveal_slot(self, room_code: str, requester_id: str, slot_index: int) -> list[Event]:
        await self._require_host(room_code, requester_id, "reveal a slot")
        engine = await self._require_engine(room_code)
        return await engine.handle_command(RevealSlotCommand(player_id=requester_id, slot_index=slot_index))

    async def strike(self, room_code: str, requester_id: str) -> list[Event]:
        await self._require_host(room_code, requester_id, "add a strike")
        engine = await self._require_engine(room_code)
        return await engine.handle_command(StrikeCommand(player_id=requester_id))

    async def steal_reveal(self, room_code: str, requester_id: str, slot_index: int) -> list[Event]:
        await self._require_host(room_code, requester_id, "mark steal success")
        engine = await self._require_engine(room_code)
        return await engine.handle_command(StealRevealCommand(player_id=requester_id, slot_index=slot_index))

    async def steal_miss(self, room_code: str, requester_id: str) -> list[Event]:
        await self._require_host(room_code, requester_id, "mark steal miss")
        engine = await self._require_engine(room_code)
        return await engine.handle_command(StealMissCommand(player_id=requester_id))

    async def next_round(self, room_code: str, requester_id: str) -> list[Event]:
        await self._require_host(room_code, requester_id, "advance to the next round")
        engine = await self._require_engine(room_code)
        return await engine.handle_command(NextRoundCommand(player_id=requester_id))

    async def get_phase_snapshot(self, room_code: str) -> dict[str, object] | None:
        engine = await self._engine_store.get(room_code)
        if engine is not None:
            assert isinstance(engine, FamilyFeudGameEngine)
            return engine.phase_snapshot()

        # Return a lobby state with team assignments so the frontend can show the
        # team picker while still in the lobby (before start_game is called).
        room = await self._room_manager.get_room(room_code)
        if room is None:
            return None
        teams = room.config.get("teams", {})
        return {
            "phase": "lobby",
            "round_number": 0,
            "total_rounds": 0,
            "prompt": None,
            "answer_count": 0,
            "board": [],
            "controlling_team": None,
            "strikes": 0,
            "team_scores": {"a": 0, "b": 0},
            "team_of": teams,
        }

    async def _require_host(self, room_code: str, requester_id: str, action: str) -> None:
        room = await self._room_manager.require_room(room_code)
        if room.host_player_id != requester_id:
            raise PermissionDeniedError(f"Only the host can {action}")

    async def _require_engine(self, room_code: str) -> FamilyFeudGameEngine:
        engine = await self._engine_store.get(room_code)
        if engine is None:
            raise GameNotStartedError("The game hasn't started yet")
        assert isinstance(engine, FamilyFeudGameEngine)
        return engine


game_session_manager = GameSessionManager(room_manager, GameEngineStore(InMemoryStore()))
