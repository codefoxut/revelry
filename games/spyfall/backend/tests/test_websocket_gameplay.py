import asyncio

import pytest
from fastapi.testclient import TestClient

from app.games.spyfall.locations import LOCATION_REGISTRY
from app.main import app
from app.platform.game_session_manager import GameSessionManager
from app.platform.night_timer import NightTimerManager
from app.platform.room_manager import RoomManager
from app.platform.stores.game_engine_store import GameEngineStore
from app.platform.stores.in_memory import InMemoryStore
from app.platform.stores.room_store import RoomStore
from app.routers.rooms import get_room_manager
from app.routers.ws import get_connection_manager, get_game_session_manager, get_night_timer_manager
from app.websocket.connection_manager import ConnectionManager

# Tests wrap TestClient in `with client:` so the ASGI lifespan/portal tears
# down deterministically, cancelling any still-pending discussion timer
# (e.g. tests that end mid-DISCUSSION) instead of leaving it to run out its
# full duration in the background. Long relative to a test's own runtime so
# it never legitimately fires first.
_INERT_DURATION_SECONDS = 10.0


@pytest.fixture
def isolated_manager():
    test_manager = RoomManager(RoomStore(InMemoryStore()))
    test_connections = ConnectionManager()
    test_sessions = GameSessionManager(test_manager, GameEngineStore(InMemoryStore()))
    test_night_timer = NightTimerManager(duration_seconds=_INERT_DURATION_SECONDS)
    app.dependency_overrides[get_room_manager] = lambda: test_manager
    app.dependency_overrides[get_connection_manager] = lambda: test_connections
    app.dependency_overrides[get_game_session_manager] = lambda: test_sessions
    app.dependency_overrides[get_night_timer_manager] = lambda: test_night_timer
    yield test_manager
    test_night_timer.cancel_all()
    app.dependency_overrides.pop(get_room_manager, None)
    app.dependency_overrides.pop(get_connection_manager, None)
    app.dependency_overrides.pop(get_game_session_manager, None)
    app.dependency_overrides.pop(get_night_timer_manager, None)


def _create_room(manager: RoomManager):
    return asyncio.run(manager.create_room(game_type="spyfall", host_display_name="Alice"))


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


def _start_game_and_collect_assignments(sockets: dict, host_socket, **start_payload):
    """Sends start_game, drains each socket's role_assigned/room_state/
    discussion_timer_started triple, and returns {player_id: (is_spy, location, role)}."""
    host_socket.send_json({"type": "start_game", **start_payload})
    assignments = {}
    for player_id, socket in sockets.items():
        role_event = socket.receive_json()  # role_assigned
        assignments[player_id] = (role_event["is_spy"], role_event["location"], role_event["role"])
        socket.receive_json()  # room_state (discussion, round 1)
    for socket in sockets.values():
        socket.receive_json()  # discussion_timer_started
    return assignments


def _advance_to_voting(sockets: dict, host_socket):
    host_socket.send_json({"type": "advance_phase"})
    for socket in sockets.values():
        socket.receive_json()  # room_state (voting)


def test_cast_vote_broadcasts_and_game_over_follows_advance(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"P{i}")[1] for i in range(3)]
    client = TestClient(app)

    with client, \
         client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
        sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
        _drain_connect_messages(host_socket, g0, g1, g2)

        assignments = _start_game_and_collect_assignments(sockets, host_socket)
        spy_id = next(pid for pid, (is_spy, _, _) in assignments.items() if is_spy)

        _advance_to_voting(sockets, host_socket)

        host_socket.send_json({"type": "cast_vote", "target_player_id": spy_id})
        vote_events = [socket.receive_json() for socket in sockets.values()]
        for event in vote_events:
            assert event["type"] == "vote_cast"
            assert event["player_id"] == host_id
            assert event["target_player_id"] == spy_id

        host_socket.send_json({"type": "advance_phase"})  # VOTING -> GAME_OVER
        for socket in sockets.values():
            game_over = socket.receive_json()
            assert game_over["type"] == "game_over"
            assert game_over["winning_side"] == "non_spies"
            assert game_over["accused_player_id"] == spy_id
            socket.receive_json()  # room_state


def test_game_over_broadcasts_a_full_role_reveal_to_every_socket(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"P{i}")[1] for i in range(3)]
    client = TestClient(app)

    with client, \
         client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
        sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
        all_ids = set(sockets)
        _drain_connect_messages(host_socket, g0, g1, g2)

        assignments = _start_game_and_collect_assignments(sockets, host_socket)
        spy_id = next(pid for pid, (is_spy, _, _) in assignments.items() if is_spy)

        _advance_to_voting(sockets, host_socket)

        # Every non-spy player votes the spy out, so this resolves to a
        # non-spy win regardless of who the spy is.
        voter_ids = [pid for pid in all_ids if pid != spy_id]
        for voter_id in voter_ids:
            sockets[voter_id].send_json({"type": "cast_vote", "target_player_id": spy_id})
            for socket in sockets.values():
                socket.receive_json()  # vote_cast

        host_socket.send_json({"type": "advance_phase"})  # VOTING -> GAME_OVER
        for socket in sockets.values():
            game_over = socket.receive_json()
            assert game_over["type"] == "game_over"
            assert game_over["winning_side"] == "non_spies"
            assert game_over["accused_player_id"] == spy_id
            assert game_over["spy_player_ids"] == [spy_id]
            assert game_over["location"]
            reveal_by_player = {reveal["player_id"]: reveal for reveal in game_over["reveals"]}
            assert set(reveal_by_player) == all_ids
            assert reveal_by_player[spy_id]["is_spy"] is True
            assert reveal_by_player[spy_id]["role"] is None
            socket.receive_json()  # room_state


def test_start_game_with_a_restricted_location_assigns_only_that_location(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"P{i}")[1] for i in range(3)]
    client = TestClient(app)

    with client, \
         client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
        sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
        _drain_connect_messages(host_socket, g0, g1, g2)

        assignments = _start_game_and_collect_assignments(
            sockets, host_socket, enabled_location_keys=["airplane"]
        )

        airplane = LOCATION_REGISTRY["airplane"]
        for is_spy, location, role in assignments.values():
            if is_spy:
                assert location is None
                assert role is None
            else:
                assert location == airplane.display_name
                assert role in airplane.roles


def test_start_game_with_an_unknown_location_key_returns_invalid_payload_error(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    for i in range(3):
        _join_room(isolated_manager, room.code, display_name=f"P{i}")
    client = TestClient(app)

    with client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket:
        host_socket.receive_json()  # initial room_state
        host_socket.send_json({"type": "start_game", "enabled_location_keys": ["mars_base"]})
        error_event = host_socket.receive_json()

    assert error_event["type"] == "error"
    assert error_event["code"] == "invalid_payload"


def test_guess_location_correctly_ends_the_game_with_a_spy_win(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"P{i}")[1] for i in range(3)]
    client = TestClient(app)

    with client, \
         client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
        sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
        _drain_connect_messages(host_socket, g0, g1, g2)

        assignments = _start_game_and_collect_assignments(
            sockets, host_socket, enabled_location_keys=["airplane"]
        )
        spy_id = next(pid for pid, (is_spy, _, _) in assignments.items() if is_spy)

        sockets[spy_id].send_json({"type": "guess_location", "location_key": "airplane"})
        for socket in sockets.values():
            game_over = socket.receive_json()
            assert game_over["type"] == "game_over"
            assert game_over["winning_side"] == "spies"
            assert game_over["accused_player_id"] is None
            socket.receive_json()  # room_state


def test_guess_location_incorrectly_ends_the_game_with_a_non_spy_win(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"P{i}")[1] for i in range(3)]
    client = TestClient(app)

    with client, \
         client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
        sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
        _drain_connect_messages(host_socket, g0, g1, g2)

        assignments = _start_game_and_collect_assignments(
            sockets, host_socket, enabled_location_keys=["airplane"]
        )
        spy_id = next(pid for pid, (is_spy, _, _) in assignments.items() if is_spy)

        sockets[spy_id].send_json({"type": "guess_location", "location_key": "bank"})
        for socket in sockets.values():
            game_over = socket.receive_json()
            assert game_over["type"] == "game_over"
            assert game_over["winning_side"] == "non_spies"
            assert game_over["accused_player_id"] is None
            socket.receive_json()  # room_state


def test_guess_location_by_a_non_spy_returns_invalid_game_state(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"P{i}")[1] for i in range(3)]
    client = TestClient(app)

    with client, \
         client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
        sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
        _drain_connect_messages(host_socket, g0, g1, g2)

        assignments = _start_game_and_collect_assignments(
            sockets, host_socket, enabled_location_keys=["airplane"]
        )
        non_spy_id = next(pid for pid, (is_spy, _, _) in assignments.items() if not is_spy)

        sockets[non_spy_id].send_json({"type": "guess_location", "location_key": "airplane"})
        response = sockets[non_spy_id].receive_json()

    assert response["type"] == "error"
    assert response["code"] == "invalid_game_state"


def test_tied_vote_results_in_the_spy_evading(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"P{i}")[1] for i in range(3)]
    client = TestClient(app)

    with client, \
         client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
         client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
        sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
        all_ids = list(sockets)
        _drain_connect_messages(host_socket, g0, g1, g2)

        _start_game_and_collect_assignments(sockets, host_socket)
        _advance_to_voting(sockets, host_socket)

        # Two players each vote for a different target -> a tie with no
        # single plurality winner.
        sockets[all_ids[0]].send_json({"type": "cast_vote", "target_player_id": all_ids[1]})
        for socket in sockets.values():
            socket.receive_json()  # vote_cast
        sockets[all_ids[2]].send_json({"type": "cast_vote", "target_player_id": all_ids[3]})
        for socket in sockets.values():
            socket.receive_json()  # vote_cast

        host_socket.send_json({"type": "advance_phase"})  # VOTING -> GAME_OVER
        for socket in sockets.values():
            game_over = socket.receive_json()
            assert game_over["type"] == "game_over"
            assert game_over["winning_side"] == "spies"
            assert game_over["accused_player_id"] is None
            socket.receive_json()  # room_state


def test_cast_vote_before_game_started_returns_game_not_started(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    for i in range(3):
        _join_room(isolated_manager, room.code, display_name=f"Player{i}")
    client = TestClient(app)

    with client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "cast_vote", "target_player_id": host_id})
        response = socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "game_not_started"


def test_cast_vote_during_discussion_phase_returns_invalid_game_state(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    for i in range(3):
        _join_room(isolated_manager, room.code, display_name=f"Player{i}")
    client = TestClient(app)

    with client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "start_game"})
        socket.receive_json()  # role_assigned
        socket.receive_json()  # room_state (discussion)
        socket.receive_json()  # discussion_timer_started

        socket.send_json({"type": "cast_vote", "target_player_id": host_id})
        response = socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "invalid_game_state"
