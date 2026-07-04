import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.platform.room_manager import RoomManager
from app.platform.stores.in_memory import InMemoryStore
from app.platform.stores.room_store import RoomStore
from app.routers.rooms import get_room_manager
from app.routers.ws import get_connection_manager
from app.websocket.connection_manager import ConnectionManager


@pytest.fixture
def isolated_manager():
    """Fresh RoomManager + ConnectionManager per test, isolated from the
    module-level singletons and from other tests (same pattern as the REST
    router tests: bind the instance to a variable, not construct it inside
    the override lambda).
    """
    test_manager = RoomManager(RoomStore(InMemoryStore()))
    test_connections = ConnectionManager()
    app.dependency_overrides[get_room_manager] = lambda: test_manager
    app.dependency_overrides[get_connection_manager] = lambda: test_connections
    yield test_manager
    app.dependency_overrides.pop(get_room_manager, None)
    app.dependency_overrides.pop(get_connection_manager, None)


def _create_room(manager: RoomManager):
    return asyncio.run(manager.create_room(game_type="mafia", host_display_name="Alice"))


def _join_room(manager: RoomManager, code: str):
    return asyncio.run(manager.join_room(code, display_name="Bob"))


def test_connect_receives_initial_room_state(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        event = socket.receive_json()

    assert event["type"] == "room_state"
    assert event["room"]["code"] == room.code
    assert event["room"]["players"][0]["id"] == host_id


def test_second_connection_broadcasts_presence_to_first(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket:
        host_socket.receive_json()  # initial room_state

        with client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
            guest_socket.receive_json()  # guest's own initial room_state
            presence_event = host_socket.receive_json()

    assert presence_event["type"] == "player_connection_changed"
    assert presence_event["player_id"] == guest_id
    assert presence_event["connected"] is True


def test_unknown_room_closes_connection(isolated_manager):
    client = TestClient(app)

    with pytest.raises(Exception):
        with client.websocket_connect("/ws/ZZZZZ?player_id=nobody") as socket:
            socket.receive_json()


def test_ping_receives_pong(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "ping"})
        response = socket.receive_json()

    assert response == {"type": "pong"}


def test_unrecognized_event_receives_error(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "not_a_real_event"})
        response = socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "unknown_event"


def test_set_ready_broadcasts_room_state_to_everyone(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket:
        host_socket.receive_json()  # initial room_state

        with client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
            guest_socket.receive_json()  # guest's own initial room_state
            host_socket.receive_json()  # presence broadcast for guest joining

            guest_socket.send_json({"type": "set_ready", "ready": True})
            host_update = host_socket.receive_json()
            guest_update = guest_socket.receive_json()

    for event in (host_update, guest_update):
        assert event["type"] == "room_state"
        players_by_id = {p["id"]: p for p in event["room"]["players"]}
        assert players_by_id[guest_id]["is_ready"] is True


def test_update_profile_changes_display_name(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "update_profile", "display_name": "Alicia"})
        update = socket.receive_json()

    assert update["room"]["players"][0]["display_name"] == "Alicia"


def test_non_host_kick_is_rejected(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
        guest_socket.receive_json()  # initial room_state
        guest_socket.send_json({"type": "kick_player", "target_player_id": host_id})
        response = guest_socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "permission_denied"


def test_host_kick_closes_target_socket_and_broadcasts(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket:
        host_socket.receive_json()  # initial room_state

        with client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
            guest_socket.receive_json()  # guest's own initial room_state
            host_socket.receive_json()  # presence broadcast for guest joining

            host_socket.send_json({"type": "kick_player", "target_player_id": guest_id})
            kicked_event = guest_socket.receive_json()
            room_update = host_socket.receive_json()

    assert kicked_event["type"] == "kicked"
    assert room_update["type"] == "room_state"
    assert all(p["id"] != guest_id for p in room_update["room"]["players"])


def test_leave_room_removes_player_and_broadcasts(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket:
        host_socket.receive_json()  # initial room_state

        with client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
            guest_socket.receive_json()  # guest's own initial room_state
            host_socket.receive_json()  # presence broadcast for guest joining

            guest_socket.send_json({"type": "leave_room"})
            room_update = host_socket.receive_json()

    assert room_update["type"] == "room_state"
    assert all(p["id"] != guest_id for p in room_update["room"]["players"])
