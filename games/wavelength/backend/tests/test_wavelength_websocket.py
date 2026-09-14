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
    return asyncio.run(manager.create_room(game_type="wavelength", host_display_name="Alice"))


def _join_room(manager: RoomManager, code: str, name: str = "Bob"):
    return asyncio.run(manager.join_room(code, display_name=name))


def test_connect_receives_initial_room_state(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        event = socket.receive_json()
    assert event["type"] == "room_state"
    assert event["room"]["code"] == room.code


def test_ping_pong(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}


def test_start_game_with_too_few_players_rejected(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()
        socket.send_json({"type": "start_game"})
        response = socket.receive_json()
    assert response["type"] == "error"
    assert response["code"] == "not_enough_players"


def test_non_host_cannot_start_game(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, g0 = _join_room(isolated_manager, room.code, "P1")
    _, g1 = _join_room(isolated_manager, room.code, "P2")
    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={g0}") as socket:
        socket.receive_json()
        socket.send_json({"type": "start_game"})
        response = socket.receive_json()
    assert response["type"] == "error"
    assert response["code"] == "permission_denied"


def _start_wavelength_game(client, room, host_id, guest_ids):
    """Helper: connect all players, start the game, drain initial messages.

    Returns:
        sockets: dict of player_id -> socket
        psychic_id: the ID of the first psychic
    """
    all_ids = [host_id] + guest_ids
    sockets = {}
    cms = []

    for pid in all_ids:
        cm = client.websocket_connect(f"/ws/{room.code}?player_id={pid}")
        ws = cm.__enter__()
        cms.append((cm, ws))
        sockets[pid] = ws

    # Drain initial room_state for each player (and presence broadcasts)
    for pid in all_ids:
        sockets[pid].receive_json()  # own room_state

    # Drain presence broadcasts (each subsequent join triggers one per already-connected socket)
    for i in range(1, len(all_ids)):
        for j in range(i):
            sockets[all_ids[j]].receive_json()

    # Start game
    sockets[host_id].send_json({"type": "start_game"})

    # Collect room_state broadcast and psychic_target (for psychic only)
    psychic_id = None
    for pid in all_ids:
        msg = sockets[pid].receive_json()
        # First message after start might be psychic_target (for psychic) or room_state
        if msg["type"] == "psychic_target":
            psychic_id = pid
            sockets[pid].receive_json()  # room_state follows
        else:
            assert msg["type"] == "room_state"

    return sockets, psychic_id, cms


def test_start_game_sends_psychic_target_only_to_psychic(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, g0 = _join_room(isolated_manager, room.code, "P1")
    _, g1 = _join_room(isolated_manager, room.code, "P2")
    all_ids = [host_id, g0, g1]

    with TestClient(app) as client:
        sockets = {}
        for pid in all_ids:
            ws = client.websocket_connect(f"/ws/{room.code}?player_id={pid}").__enter__()
            sockets[pid] = ws

        for pid in all_ids:
            sockets[pid].receive_json()  # own room_state
        for i in range(1, len(all_ids)):
            for j in range(i):
                sockets[all_ids[j]].receive_json()  # presence broadcasts

        sockets[host_id].send_json({"type": "start_game"})

        # Collect all messages from all sockets
        received: dict[str, list] = {pid: [] for pid in all_ids}
        for pid in all_ids:
            # Expect room_state + possibly psychic_target
            msg1 = sockets[pid].receive_json()
            received[pid].append(msg1)
            if msg1["type"] == "psychic_target":
                msg2 = sockets[pid].receive_json()  # room_state
                received[pid].append(msg2)

        # Exactly one player should have received a psychic_target
        psychic_receivers = [pid for pid, msgs in received.items() if any(m["type"] == "psychic_target" for m in msgs)]
        assert len(psychic_receivers) == 1, "Exactly one player (the Psychic) should receive psychic_target"

        # Non-psychics must NOT have received psychic_target
        for pid in all_ids:
            if pid not in psychic_receivers:
                assert all(m["type"] != "psychic_target" for m in received[pid]), (
                    f"Non-psychic {pid} received a psychic_target event"
                )


def test_non_psychic_submit_guess_accepted(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, g0 = _join_room(isolated_manager, room.code, "P1")
    _, g1 = _join_room(isolated_manager, room.code, "P2")
    all_ids = [host_id, g0, g1]

    with TestClient(app) as client:
        sockets = {}
        for pid in all_ids:
            sockets[pid] = client.websocket_connect(f"/ws/{room.code}?player_id={pid}").__enter__()

        for pid in all_ids:
            sockets[pid].receive_json()
        for i in range(1, len(all_ids)):
            for j in range(i):
                sockets[all_ids[j]].receive_json()

        sockets[host_id].send_json({"type": "start_game"})

        psychic_id = None
        for pid in all_ids:
            msg = sockets[pid].receive_json()
            if msg["type"] == "psychic_target":
                psychic_id = pid
                sockets[pid].receive_json()  # room_state
            # else it's the room_state broadcast

        assert psychic_id is not None
        guesser = next(pid for pid in all_ids if pid != psychic_id)

        # Psychic gives clue
        sockets[psychic_id].send_json({"type": "give_clue", "clue_text": "warm"})
        for pid in all_ids:
            sockets[pid].receive_json()  # clue_given
            sockets[pid].receive_json()  # room_state

        # Guesser submits
        sockets[guesser].send_json({"type": "submit_guess", "position": 55.0})
        for pid in all_ids:
            event = sockets[pid].receive_json()
            assert event["type"] == "player_guessed"


def test_psychic_cannot_submit_guess(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, g0 = _join_room(isolated_manager, room.code, "P1")
    _, g1 = _join_room(isolated_manager, room.code, "P2")
    all_ids = [host_id, g0, g1]

    with TestClient(app) as client:
        sockets = {}
        for pid in all_ids:
            sockets[pid] = client.websocket_connect(f"/ws/{room.code}?player_id={pid}").__enter__()

        for pid in all_ids:
            sockets[pid].receive_json()
        for i in range(1, len(all_ids)):
            for j in range(i):
                sockets[all_ids[j]].receive_json()

        sockets[host_id].send_json({"type": "start_game"})

        psychic_id = None
        for pid in all_ids:
            msg = sockets[pid].receive_json()
            if msg["type"] == "psychic_target":
                psychic_id = pid
                sockets[pid].receive_json()
        assert psychic_id is not None

        sockets[psychic_id].send_json({"type": "give_clue", "clue_text": "warm"})
        for pid in all_ids:
            sockets[pid].receive_json()
            sockets[pid].receive_json()

        sockets[psychic_id].send_json({"type": "submit_guess", "position": 50.0})
        response = sockets[psychic_id].receive_json()
        assert response["type"] == "error"
        assert response["code"] == "permission_denied"


def test_reconnect_resends_psychic_target(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, g0 = _join_room(isolated_manager, room.code, "P1")
    _, g1 = _join_room(isolated_manager, room.code, "P2")
    all_ids = [host_id, g0, g1]

    with TestClient(app) as client:
        sockets = {}
        for pid in all_ids:
            sockets[pid] = client.websocket_connect(f"/ws/{room.code}?player_id={pid}").__enter__()

        for pid in all_ids:
            sockets[pid].receive_json()
        for i in range(1, len(all_ids)):
            for j in range(i):
                sockets[all_ids[j]].receive_json()

        sockets[host_id].send_json({"type": "start_game"})

        psychic_id = None
        for pid in all_ids:
            msg = sockets[pid].receive_json()
            if msg["type"] == "psychic_target":
                psychic_id = pid
                original_target = msg["target_position"]
                sockets[pid].receive_json()
        assert psychic_id is not None

        # Psychic reconnects
        with client.websocket_connect(f"/ws/{room.code}?player_id={psychic_id}") as reconnect_ws:
            reconnect_ws.receive_json()  # room_state
            reconnect_event = reconnect_ws.receive_json()  # psychic_target resent

        assert reconnect_event["type"] == "psychic_target"
        assert reconnect_event["target_position"] == original_target
