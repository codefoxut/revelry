import asyncio

import pytest

from app.games.mafia import MAFIA_MODULE
from app.platform.exceptions import (
    GameAlreadyStartedError,
    GameNotStartedError,
    NotEnoughPlayersError,
    PermissionDeniedError,
)
from app.platform.game_registry import GameRegistry
from app.platform.game_session_manager import GameSessionManager
from app.platform.room import RoomPhase
from app.platform.room_manager import RoomManager
from app.platform.stores.game_engine_store import GameEngineStore
from app.platform.stores.in_memory import InMemoryStore
from app.platform.stores.room_store import RoomStore


@pytest.fixture
def sessions():
    room_manager = RoomManager(RoomStore(InMemoryStore()))
    registry = GameRegistry()
    registry.register(MAFIA_MODULE)
    return GameSessionManager(room_manager, registry, GameEngineStore(InMemoryStore())), room_manager


def _create_room_with_players(room_manager: RoomManager, extra_players: int):
    room, host_id = asyncio.run(room_manager.create_room(game_type="mafia", host_display_name="Host"))
    for i in range(extra_players):
        asyncio.run(room_manager.join_room(room.code, display_name=f"Player{i}"))
    return room, host_id


def test_start_game_requires_host(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)
    _, guest_id = asyncio.run(room_manager.join_room(room.code, display_name="Guest"))

    with pytest.raises(PermissionDeniedError):
        asyncio.run(game_sessions.start_game(room.code, guest_id))


def test_start_game_requires_minimum_players(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 1)  # 2 active players, min is 4

    with pytest.raises(NotEnoughPlayersError):
        asyncio.run(game_sessions.start_game(room.code, host_id))


def test_start_game_moves_room_to_in_game_and_night_phase(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)

    updated_room, events = asyncio.run(game_sessions.start_game(room.code, host_id))

    assert updated_room.phase == RoomPhase.IN_GAME
    assert events[0].phase.value == "night"
    snapshot = asyncio.run(game_sessions.get_phase_snapshot(room.code))
    assert snapshot == {"phase": "night", "round_number": 1}


def test_start_game_twice_is_rejected(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)
    asyncio.run(game_sessions.start_game(room.code, host_id))

    with pytest.raises(GameAlreadyStartedError):
        asyncio.run(game_sessions.start_game(room.code, host_id))


def test_advance_phase_before_start_is_rejected(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)

    with pytest.raises(GameNotStartedError):
        asyncio.run(game_sessions.advance_phase(room.code, host_id))


def test_advance_phase_requires_host(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)
    _, guest_id = asyncio.run(room_manager.join_room(room.code, display_name="Guest"))
    asyncio.run(game_sessions.start_game(room.code, host_id))

    with pytest.raises(PermissionDeniedError):
        asyncio.run(game_sessions.advance_phase(room.code, guest_id))


def test_get_phase_snapshot_is_none_before_start(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)

    assert asyncio.run(game_sessions.get_phase_snapshot(room.code)) is None
