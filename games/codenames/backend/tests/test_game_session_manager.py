import asyncio

import pytest

from app.games.codenames.board import Role
from app.platform.exceptions import (
    GameAlreadyStartedError,
    GameNotStartedError,
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
    room, host_id = asyncio.run(room_manager.create_room(game_type="codenames", host_display_name="Host"))
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
    room, host_id = _create_room_with_players(room_manager, 2)  # 3 active players, min is 4

    with pytest.raises(NotEnoughPlayersError):
        asyncio.run(game_sessions.start_game(room.code, host_id))


def test_start_game_moves_room_to_in_game_and_deals_a_board(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)

    updated_room, events = asyncio.run(game_sessions.start_game(room.code, host_id))

    assert updated_room.phase == RoomPhase.IN_GAME
    assert len(events) == 4
    snapshot = asyncio.run(game_sessions.get_phase_snapshot(room.code))
    assert snapshot["phase"] in ("red_turn", "blue_turn")
    assert snapshot["round_number"] == 1
    assert len(snapshot["board"]) == 25
    assert snapshot["red_remaining"] + snapshot["blue_remaining"] == 17


def test_start_game_twice_is_rejected(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)
    asyncio.run(game_sessions.start_game(room.code, host_id))

    with pytest.raises(GameAlreadyStartedError):
        asyncio.run(game_sessions.start_game(room.code, host_id))


def test_give_clue_before_start_is_rejected(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)

    with pytest.raises(GameNotStartedError):
        asyncio.run(game_sessions.give_clue(room.code, host_id, "ANIMAL", 2))


def test_get_phase_snapshot_is_none_before_start(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)

    assert asyncio.run(game_sessions.get_phase_snapshot(room.code)) is None


def test_get_team_assignment_is_none_before_start(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)

    assert asyncio.run(game_sessions.get_team_assignment(room.code, host_id)) is None


def test_get_team_assignment_returns_a_team_and_role_for_every_active_player_after_start(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)
    asyncio.run(game_sessions.start_game(room.code, host_id))

    spymasters = []
    for player_id in room.players:
        assignment = asyncio.run(game_sessions.get_team_assignment(room.code, player_id))
        assert assignment is not None
        team, role = assignment
        assert team.value in ("red", "blue")
        if role == Role.SPYMASTER:
            spymasters.append(team)

    assert sorted(t.value for t in spymasters) == ["blue", "red"]


def test_get_spymaster_colors_is_none_for_a_guesser(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)
    asyncio.run(game_sessions.start_game(room.code, host_id))

    guesser_id = next(
        pid
        for pid in room.players
        if asyncio.run(game_sessions.get_team_assignment(room.code, pid))[1] == Role.GUESSER
    )

    assert asyncio.run(game_sessions.get_spymaster_colors(room.code, guesser_id)) is None


def test_get_spymaster_colors_returns_the_full_board_for_a_spymaster(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)
    asyncio.run(game_sessions.start_game(room.code, host_id))

    spymaster_id = next(
        pid
        for pid in room.players
        if asyncio.run(game_sessions.get_team_assignment(room.code, pid))[1] == Role.SPYMASTER
    )

    colors = asyncio.run(game_sessions.get_spymaster_colors(room.code, spymaster_id))
    assert colors is not None
    assert len(colors) == 25


def test_give_clue_then_make_guess_reveals_a_card(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)
    asyncio.run(game_sessions.start_game(room.code, host_id))
    snapshot = asyncio.run(game_sessions.get_phase_snapshot(room.code))
    current_team = snapshot["current_team"]

    assignments = {pid: asyncio.run(game_sessions.get_team_assignment(room.code, pid)) for pid in room.players}
    spymaster_id = next(
        pid for pid, (team, role) in assignments.items() if team.value == current_team and role == Role.SPYMASTER
    )
    guesser_id = next(
        pid for pid, (team, role) in assignments.items() if team.value == current_team and role == Role.GUESSER
    )

    asyncio.run(game_sessions.give_clue(room.code, spymaster_id, "ANIMAL", 1))
    asyncio.run(game_sessions.make_guess(room.code, guesser_id, 0))

    snapshot = asyncio.run(game_sessions.get_phase_snapshot(room.code))
    assert snapshot["board"][0]["revealed"] is True


def test_end_turn_before_start_is_rejected(sessions):
    game_sessions, room_manager = sessions
    room, host_id = _create_room_with_players(room_manager, 3)

    with pytest.raises(GameNotStartedError):
        asyncio.run(game_sessions.end_turn(room.code, host_id))
