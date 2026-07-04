import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app.games.mafia import MAFIA_MODULE
from app.main import app
from app.platform.disconnect_grace import DisconnectGraceManager
from app.platform.game_registry import GameRegistry
from app.platform.game_session_manager import GameSessionManager
from app.platform.room_manager import RoomManager
from app.platform.stores.game_engine_store import GameEngineStore
from app.platform.stores.in_memory import InMemoryStore
from app.platform.stores.room_store import RoomStore
from app.routers.rooms import get_room_manager
from app.routers.ws import get_connection_manager, get_disconnect_grace_manager, get_game_session_manager
from app.websocket.connection_manager import ConnectionManager

_FAST_GRACE_SECONDS = 0.05


@pytest.fixture
def isolated_manager():
    test_manager = RoomManager(RoomStore(InMemoryStore()))
    test_connections = ConnectionManager()
    test_registry = GameRegistry()
    test_registry.register(MAFIA_MODULE)
    test_sessions = GameSessionManager(test_manager, test_registry, GameEngineStore(InMemoryStore()))
    test_grace = DisconnectGraceManager(grace_seconds=_FAST_GRACE_SECONDS)
    app.dependency_overrides[get_room_manager] = lambda: test_manager
    app.dependency_overrides[get_connection_manager] = lambda: test_connections
    app.dependency_overrides[get_game_session_manager] = lambda: test_sessions
    app.dependency_overrides[get_disconnect_grace_manager] = lambda: test_grace
    yield test_manager
    test_grace.cancel_all()
    app.dependency_overrides.pop(get_room_manager, None)
    app.dependency_overrides.pop(get_connection_manager, None)
    app.dependency_overrides.pop(get_game_session_manager, None)
    app.dependency_overrides.pop(get_disconnect_grace_manager, None)


def _create_room(manager: RoomManager):
    return asyncio.run(manager.create_room(game_type="mafia", host_display_name="Alice"))


def _join_room(manager: RoomManager, code: str, display_name: str = "Bob"):
    return asyncio.run(manager.join_room(code, display_name=display_name))


def test_disconnected_player_is_removed_from_lobby_after_grace_period(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)
    client = TestClient(app)

    # `with client:` keeps one shared portal (and its event loop thread)
    # alive for the whole test, so the grace-period asyncio task scheduled
    # on the guest's disconnect keeps running after the guest socket closes
    # — without this, each `websocket_connect` gets its own short-lived
    # portal that's torn down (cancelling any pending tasks) the moment
    # that particular connection's `with` block exits.
    with client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket:
            host_socket.receive_json()  # initial room_state

            with client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
                guest_socket.receive_json()  # guest's own initial room_state
                host_socket.receive_json()  # presence: guest connected

            presence_disconnected = host_socket.receive_json()  # presence: guest disconnected

            time.sleep(_FAST_GRACE_SECONDS * 6)  # long enough for the grace timer to fire
            removal_update = host_socket.receive_json()

    assert presence_disconnected["type"] == "player_connection_changed"
    assert presence_disconnected["connected"] is False
    assert removal_update["type"] == "room_state"
    assert all(p["id"] != guest_id for p in removal_update["room"]["players"])


def test_reconnect_within_grace_period_prevents_removal(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)
    client = TestClient(app)

    with client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket:
            host_socket.receive_json()  # initial room_state

            with client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
                guest_socket.receive_json()
                host_socket.receive_json()  # presence: connected True

            host_socket.receive_json()  # presence: connected False

            with client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket_2:
                guest_socket_2.receive_json()  # own room_state on reconnect
                host_socket.receive_json()  # presence: connected True again

                time.sleep(_FAST_GRACE_SECONDS * 6)  # past when the original timer would've fired

                room_after = asyncio.run(isolated_manager.get_room(room.code))
                assert guest_id in room_after.players


def test_disconnect_during_active_game_is_not_removed(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"P{i}")[1] for i in range(3)]
    client = TestClient(app)

    with client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket:
            host_socket.receive_json()  # initial room_state
            host_socket.send_json({"type": "start_game"})
            host_socket.receive_json()  # role_assigned
            host_socket.receive_json()  # room_state: in_game/night

            with client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as guest_socket:
                guest_socket.receive_json()  # own room_state
                guest_socket.receive_json()  # own role_assigned (resent on connect)
                host_socket.receive_json()  # presence: connected True

            host_socket.receive_json()  # presence: connected False

            time.sleep(_FAST_GRACE_SECONDS * 6)
            room_after = asyncio.run(isolated_manager.get_room(room.code))
            assert guest_ids[0] in room_after.players
