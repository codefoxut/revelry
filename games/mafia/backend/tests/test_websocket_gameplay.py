import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.platform.game_session_manager import GameSessionManager
from app.platform.room_manager import RoomManager
from app.platform.stores.game_engine_store import GameEngineStore
from app.platform.stores.in_memory import InMemoryStore
from app.platform.stores.room_store import RoomStore
from app.routers.rooms import get_room_manager
from app.routers.ws import get_connection_manager, get_game_session_manager
from app.websocket.connection_manager import ConnectionManager


@pytest.fixture
def isolated_manager():
    test_manager = RoomManager(RoomStore(InMemoryStore()))
    test_connections = ConnectionManager()
    test_sessions = GameSessionManager(test_manager, GameEngineStore(InMemoryStore()))
    app.dependency_overrides[get_room_manager] = lambda: test_manager
    app.dependency_overrides[get_connection_manager] = lambda: test_connections
    app.dependency_overrides[get_game_session_manager] = lambda: test_sessions
    yield test_manager
    app.dependency_overrides.pop(get_room_manager, None)
    app.dependency_overrides.pop(get_connection_manager, None)
    app.dependency_overrides.pop(get_game_session_manager, None)


def _create_room(manager: RoomManager):
    return asyncio.run(manager.create_room(game_type="mafia", host_display_name="Alice"))


def _join_room(manager: RoomManager, code: str, display_name: str = "Bob"):
    return asyncio.run(manager.join_room(code, display_name=display_name))


def _drain_connect_messages(*sockets_in_connection_order):
    """Each socket's own initial room_state arrives first, followed by one
    presence broadcast for every socket that connects after it. Drain
    exactly those so tests can start from a known, empty queue.
    """
    for index, socket in enumerate(sockets_in_connection_order):
        socket.receive_json()  # own initial room_state
        for _ in range(len(sockets_in_connection_order) - index - 1):
            socket.receive_json()  # presence: a later socket connected


def test_cast_vote_broadcasts_and_elimination_result_follows_advance(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"P{i}")[1] for i in range(3)]
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
        sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
        _drain_connect_messages(host_socket, g0, g1, g2)

        host_socket.send_json({"type": "start_game"})
        roles_by_player = {}
        for player_id, socket in sockets.items():
            role_event = socket.receive_json()  # role_assigned
            roles_by_player[player_id] = role_event["role"]["team"]
            socket.receive_json()  # room_state (night, round 1)
        for socket in sockets.values():
            socket.receive_json()  # night_timer_started

        # Give the mafia an explicit, locked target so the night resolves
        # deterministically rather than falling back to a random villager —
        # picked to avoid guest_ids[0] and the host, since both are needed
        # alive for the voting assertions below.
        mafia_id = next(pid for pid, team in roles_by_player.items() if team == "mafia")
        safe_target = next(pid for pid in (guest_ids[1], guest_ids[2]) if pid != mafia_id)
        sockets[mafia_id].send_json({"type": "night_action", "target_player_id": safe_target})
        sockets[mafia_id].receive_json()  # mafia_night_picks echo
        sockets[mafia_id].send_json({"type": "lock_night_action"})
        sockets[mafia_id].receive_json()  # mafia_night_picks echo

        host_socket.send_json({"type": "advance_phase"})  # NIGHT -> DAY
        for socket in (host_socket, g0, g1, g2):
            socket.receive_json()  # night_result
            socket.receive_json()  # room_state

        host_socket.send_json({"type": "advance_phase"})  # DAY -> VOTING
        for socket in (host_socket, g0, g1, g2):
            socket.receive_json()  # room_state

        host_socket.send_json({"type": "cast_vote", "target_player_id": guest_ids[0]})
        vote_events = [socket.receive_json() for socket in (host_socket, g0, g1, g2)]
        for event in vote_events:
            assert event["type"] == "vote_cast"
            assert event["player_id"] == host_id
            assert event["target_player_id"] == guest_ids[0]

        host_socket.send_json({"type": "advance_phase"})  # VOTING -> ELIMINATION
        elimination_events = [socket.receive_json() for socket in (host_socket, g0, g1, g2)]
        for event in elimination_events:
            assert event["type"] == "elimination_result"
            # only one vote was cast, so the plurality target is eliminated
            assert event["eliminated_player_id"] == guest_ids[0]
        for socket in (host_socket, g0, g1, g2):
            socket.receive_json()  # room_state


def test_game_over_broadcasts_a_full_role_reveal_to_every_socket(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"P{i}")[1] for i in range(3)]
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
        sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
        all_ids = set(sockets)
        _drain_connect_messages(host_socket, g0, g1, g2)

        host_socket.send_json({"type": "start_game"})
        roles_by_player = {}
        for player_id, socket in sockets.items():
            role_event = socket.receive_json()  # role_assigned
            roles_by_player[player_id] = role_event["role"]
            socket.receive_json()  # room_state (night, round 1)
        for socket in sockets.values():
            socket.receive_json()  # night_timer_started

        mafia_id = next(pid for pid, role in roles_by_player.items() if role["team"] == "mafia")
        night_target = next(pid for pid in all_ids if pid != mafia_id)
        sockets[mafia_id].send_json({"type": "night_action", "target_player_id": night_target})
        sockets[mafia_id].receive_json()  # mafia_night_picks echo
        sockets[mafia_id].send_json({"type": "lock_night_action"})
        sockets[mafia_id].receive_json()  # mafia_night_picks echo

        host_socket.send_json({"type": "advance_phase"})  # NIGHT -> DAY
        for socket in sockets.values():
            socket.receive_json()  # night_result
            socket.receive_json()  # room_state

        host_socket.send_json({"type": "advance_phase"})  # DAY -> VOTING
        for socket in sockets.values():
            socket.receive_json()  # room_state

        # Every alive non-mafia player votes the mafia out, so this
        # resolves to a town win regardless of who died overnight.
        voter_ids = [pid for pid in all_ids if pid != mafia_id and pid != night_target]
        for voter_id in voter_ids:
            sockets[voter_id].send_json({"type": "cast_vote", "target_player_id": mafia_id})
            for socket in sockets.values():
                socket.receive_json()  # vote_cast

        host_socket.send_json({"type": "advance_phase"})  # VOTING -> ELIMINATION
        for socket in sockets.values():
            elimination_result = socket.receive_json()
            assert elimination_result["eliminated_player_id"] == mafia_id
            socket.receive_json()  # room_state

        host_socket.send_json({"type": "advance_phase"})  # ELIMINATION -> GAME_OVER
        for socket in sockets.values():
            game_over = socket.receive_json()
            assert game_over["type"] == "game_over"
            assert game_over["winning_team"] == "town"
            reveal_by_player = {reveal["player_id"]: reveal for reveal in game_over["roles"]}
            assert set(reveal_by_player) == all_ids
            assert reveal_by_player[mafia_id]["role_key"] == "mafia"
            assert reveal_by_player[mafia_id]["team"] == "mafia"
            socket.receive_json()  # room_state


def test_night_action_delivers_investigation_result_only_to_detective(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"P{i}")[1] for i in range(3)]
    client = TestClient(app)
    all_ids = [host_id, *guest_ids]

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
        sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
        _drain_connect_messages(host_socket, g0, g1, g2)

        host_socket.send_json({"type": "start_game"})
        roles_by_player = {}
        for player_id, socket in sockets.items():
            role_event = socket.receive_json()
            roles_by_player[player_id] = role_event["role"]["key"]
            socket.receive_json()  # room_state
        for socket in sockets.values():
            socket.receive_json()  # night_timer_started

        detective_id = next(pid for pid, role in roles_by_player.items() if role == "detective")
        mafia_id = next(pid for pid, role in roles_by_player.items() if role == "mafia")

        sockets[detective_id].send_json({"type": "night_action", "target_player_id": mafia_id})
        result = sockets[detective_id].receive_json()
        assert result["type"] == "investigation_result"
        assert result["target_player_id"] == mafia_id
        assert result["team"] == "mafia"

        # confirm no room_state rebroadcast was queued for the detective by
        # having them ping and checking pong is the very next message
        sockets[detective_id].send_json({"type": "ping"})
        assert sockets[detective_id].receive_json()["type"] == "pong"


def test_mafia_night_picks_only_delivered_to_mafia_team(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"P{i}")[1] for i in range(3)]
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
        sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
        _drain_connect_messages(host_socket, g0, g1, g2)

        host_socket.send_json({"type": "start_game"})
        roles_by_player = {}
        for player_id, socket in sockets.items():
            role_event = socket.receive_json()
            roles_by_player[player_id] = role_event["role"]["key"]
            socket.receive_json()  # room_state
        for socket in sockets.values():
            socket.receive_json()  # night_timer_started

        mafia_id = next(pid for pid, role in roles_by_player.items() if role == "mafia")
        other_target = next(pid for pid in sockets if pid != mafia_id)

        sockets[mafia_id].send_json({"type": "night_action", "target_player_id": other_target})
        picks_event = sockets[mafia_id].receive_json()
        assert picks_event["type"] == "mafia_night_picks"
        assert [p["player_id"] for p in picks_event["picks"]] == [mafia_id]
        assert picks_event["picks"][0]["locked"] is False

        sockets[mafia_id].send_json({"type": "lock_night_action"})
        locked_event = sockets[mafia_id].receive_json()
        assert locked_event["picks"][0]["locked"] is True

        # No non-mafia socket should ever receive a mafia_night_picks event —
        # confirm each of them still gets pong as their very next message.
        for pid, socket in sockets.items():
            if pid == mafia_id:
                continue
            socket.send_json({"type": "ping"})
            assert socket.receive_json()["type"] == "pong"


def test_night_action_invalid_payload_returns_error(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    for i in range(3):
        _join_room(isolated_manager, room.code, display_name=f"Player{i}")
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "start_game"})
        socket.receive_json()  # role_assigned
        socket.receive_json()  # room_state
        socket.receive_json()  # night_timer_started

        socket.send_json({"type": "night_action"})
        response = socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "invalid_payload"


def test_cast_vote_before_game_started_returns_game_not_started(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    for i in range(3):
        _join_room(isolated_manager, room.code, display_name=f"Player{i}")
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "cast_vote", "target_player_id": host_id})
        response = socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "game_not_started"


def test_night_action_wrong_phase_returns_invalid_game_state(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    for i in range(3):
        _join_room(isolated_manager, room.code, display_name=f"Player{i}")
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "start_game"})
        socket.receive_json()  # role_assigned
        socket.receive_json()  # room_state (night)
        socket.receive_json()  # night_timer_started

        socket.send_json({"type": "advance_phase"})  # -> DAY (or GAME_OVER, if the
        # unseeded RNG's fallback happens to kill the sole mafia)
        socket.receive_json()  # night_result
        update = socket.receive_json()
        if update["type"] != "room_state":
            socket.receive_json()  # room_state

        socket.send_json({"type": "night_action", "target_player_id": host_id})
        response = socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "invalid_game_state"
