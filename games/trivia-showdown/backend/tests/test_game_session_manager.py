import asyncio

import pytest

from app.platform.exceptions import (
    GameAlreadyStartedError,
    GameNotStartedError,
    InvalidGameStateError,
    NotEnoughPlayersError,
    PermissionDeniedError,
)
from app.platform.game_session_manager import GameSessionManager
from app.platform.room import RoomPhase
from app.platform.room_manager import RoomManager
from app.platform.stores.game_engine_store import GameEngineStore
from app.platform.stores.in_memory import InMemoryStore
from app.platform.stores.room_store import RoomStore


@pytest.fixture
def sessions():
    room_manager = RoomManager(RoomStore(InMemoryStore()))
    return GameSessionManager(room_manager, GameEngineStore(InMemoryStore())), room_manager


def _create_room_with_players(room_manager: RoomManager, extra_players: int):
    room, host_id = asyncio.run(room_manager.create_room(game_type="trivia_showdown", host_display_name="Host"))
    for i in range(extra_players):
        asyncio.run(room_manager.join_room(room.code, display_name=f"Player{i}"))
    return room, host_id


def test_start_game_requires_host(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 1)
    _, guest_id = asyncio.run(room_manager.join_room(room.code, display_name="Guest"))

    with pytest.raises(PermissionDeniedError):
        asyncio.run(game_sessions.start_game(room.code, guest_id))


def test_start_game_requires_minimum_players(sessions):
    game_sessions, room_manager = sessions
    room, host_id = asyncio.run(room_manager.create_room(game_type="trivia_showdown", host_display_name="Host"))

    with pytest.raises(NotEnoughPlayersError):
        asyncio.run(game_sessions.start_game(room.code, host_id))


def test_start_game_moves_room_to_in_game_and_opens_first_question(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 2)

    updated_room, events = asyncio.run(game_sessions.start_game(room.code, host_id))

    assert updated_room.phase == RoomPhase.IN_GAME
    assert len(events) == 1
    snapshot = asyncio.run(game_sessions.get_phase_snapshot(room.code))
    assert snapshot["phase"] == "question_open"
    assert snapshot["round_number"] == 1
    assert snapshot["scores"] == {pid: 0 for pid in room.players if pid != host_id}


def test_active_player_ids_exclude_the_host(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 2)

    asyncio.run(game_sessions.start_game(room.code, host_id))

    snapshot = asyncio.run(game_sessions.get_phase_snapshot(room.code))
    assert host_id not in snapshot["scores"]


def test_start_game_twice_is_rejected(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 2)
    asyncio.run(game_sessions.start_game(room.code, host_id))

    with pytest.raises(GameAlreadyStartedError):
        asyncio.run(game_sessions.start_game(room.code, host_id))


def test_buzz_in_before_start_is_rejected(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 2)
    guest_id = next(pid for pid in room.players if pid != host_id)

    with pytest.raises(GameNotStartedError):
        asyncio.run(game_sessions.buzz_in(room.code, guest_id))


def test_get_phase_snapshot_is_none_before_start(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 2)

    assert asyncio.run(game_sessions.get_phase_snapshot(room.code)) is None


def test_judge_answer_requires_host(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 2)
    guest_id = next(pid for pid in room.players if pid != host_id)
    asyncio.run(game_sessions.start_game(room.code, host_id))
    asyncio.run(game_sessions.buzz_in(room.code, guest_id))

    with pytest.raises(PermissionDeniedError):
        asyncio.run(game_sessions.judge_answer(room.code, guest_id, True))


def test_reveal_requires_host(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 2)
    guest_id = next(pid for pid in room.players if pid != host_id)
    asyncio.run(game_sessions.start_game(room.code, host_id))

    with pytest.raises(PermissionDeniedError):
        asyncio.run(game_sessions.reveal(room.code, guest_id))


def test_next_question_requires_host(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 2)
    guest_id = next(pid for pid in room.players if pid != host_id)
    asyncio.run(game_sessions.start_game(room.code, host_id))
    asyncio.run(game_sessions.reveal(room.code, host_id))

    with pytest.raises(PermissionDeniedError):
        asyncio.run(game_sessions.next_question(room.code, guest_id))


def test_buzz_in_then_host_judges_correct_awards_points(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 2)
    guest_id = next(pid for pid in room.players if pid != host_id)
    asyncio.run(game_sessions.start_game(room.code, host_id))

    asyncio.run(game_sessions.buzz_in(room.code, guest_id))
    asyncio.run(game_sessions.judge_answer(room.code, host_id, True))

    snapshot = asyncio.run(game_sessions.get_phase_snapshot(room.code))
    assert snapshot["phase"] == "revealed"
    assert snapshot["scores"][guest_id] == 100


def test_next_question_before_reveal_is_rejected(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 2)
    asyncio.run(game_sessions.start_game(room.code, host_id))

    with pytest.raises(InvalidGameStateError):
        asyncio.run(game_sessions.next_question(room.code, host_id))
