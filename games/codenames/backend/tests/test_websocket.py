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
    """Fresh RoomManager + ConnectionManager + GameSessionManager per test,
    isolated from the module-level singletons and from other tests (same
    pattern as the REST router tests: bind the instance to a variable, not
    construct it inside the override lambda).
    """
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
    return asyncio.run(manager.create_room(game_type="codenames", host_display_name="Alice"))


def _join_room(manager: RoomManager, code: str, display_name: str = "Bob"):
    return asyncio.run(manager.join_room(code, display_name=display_name))


def test_connect_receives_initial_room_state(isolated_manager):
    room, host_id = _create_room(isolated_manager)

    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        event = socket.receive_json()

    assert event["type"] == "room_state"
    assert event["room"]["code"] == room.code
    assert event["room"]["players"][0]["id"] == host_id


def test_second_connection_broadcasts_room_state_to_first(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket:
            host_socket.receive_json()  # initial room_state

            with client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
                guest_socket.receive_json()  # guest's own initial room_state
                presence_event = host_socket.receive_json()

    # A full room_state (not just a connected-flag update) so the host's
    # already-open socket learns about the brand-new guest player.
    assert presence_event["type"] == "room_state"
    player_ids = {player["id"] for player in presence_event["room"]["players"]}
    assert {host_id, guest_id} == player_ids
    guest_entry = next(p for p in presence_event["room"]["players"] if p["id"] == guest_id)
    assert guest_entry["connected"] is True


def test_unknown_room_closes_connection(isolated_manager):
    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/ZZZZZ?player_id=nobody") as socket:
                socket.receive_json()


def test_ping_receives_pong(isolated_manager):
    room, host_id = _create_room(isolated_manager)

    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "ping"})
        response = socket.receive_json()

    assert response == {"type": "pong"}


def test_unrecognized_event_receives_error(isolated_manager):
    room, host_id = _create_room(isolated_manager)

    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "not_a_real_event"})
        response = socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "unknown_event"


def test_set_ready_broadcasts_room_state_to_everyone(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)

    with TestClient(app) as client:
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

    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "update_profile", "display_name": "Alicia"})
        update = socket.receive_json()

    assert update["room"]["players"][0]["display_name"] == "Alicia"


def test_non_host_kick_is_rejected(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)

    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
        guest_socket.receive_json()  # initial room_state
        guest_socket.send_json({"type": "kick_player", "target_player_id": host_id})
        response = guest_socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "permission_denied"


def test_host_kick_closes_target_socket_and_broadcasts(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)

    with TestClient(app) as client:
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

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket:
            host_socket.receive_json()  # initial room_state

            with client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
                guest_socket.receive_json()  # guest's own initial room_state
                host_socket.receive_json()  # presence broadcast for guest joining

                guest_socket.send_json({"type": "leave_room"})
                room_update = host_socket.receive_json()

    assert room_update["type"] == "room_state"
    assert all(p["id"] != guest_id for p in room_update["room"]["players"])


def _start_game_and_collect_assignments(host_socket, sockets: dict):
    """Sends start_game from the host and drains, for every connected
    socket (including the host's own), its private team_assigned (+
    spymaster_view iff it's a spymaster) followed by the shared
    room_state broadcast. Returns
    ({player_id: {"team": ..., "role": ..., "colors": list | None}}, last_room_state).
    room_state is an identical payload for every connection (no per-player
    customization at the broadcast layer), so any one of them stands in
    for "the" update.
    """
    host_socket.send_json({"type": "start_game"})

    assignments = {}
    room_state = None
    for player_id, socket in sockets.items():
        team_assigned = socket.receive_json()
        assert team_assigned["type"] == "team_assigned"
        colors = None
        if team_assigned["role"] == "spymaster":
            spymaster_view = socket.receive_json()
            assert spymaster_view["type"] == "spymaster_view"
            colors = spymaster_view["colors"]
        room_state = socket.receive_json()  # room_state broadcast
        assignments[player_id] = {"team": team_assigned["team"], "role": team_assigned["role"], "colors": colors}

    return assignments, room_state


def test_start_game_with_enough_players_broadcasts_a_team_turn(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"Player{i}")[1] for i in range(3)]

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
            host_socket.receive_json()  # own initial room_state
            g0.receive_json()
            host_socket.receive_json()  # presence: g0 joined
            g1.receive_json()
            host_socket.receive_json()  # presence: g1 joined
            g0.receive_json()  # presence: g1 joined
            g2.receive_json()
            host_socket.receive_json()  # presence: g2 joined
            g0.receive_json()  # presence: g2 joined
            g1.receive_json()  # presence: g2 joined

            sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
            assignments, update = _start_game_and_collect_assignments(host_socket, sockets)

    assert update["type"] == "room_state"
    assert update["room"]["phase"] == "in_game"
    game_state = update["room"]["game_state"]
    assert game_state["phase"] in ("red_turn", "blue_turn")
    assert game_state["round_number"] == 1
    assert len(game_state["board"]) == 25
    assert all(card["color"] is None for card in game_state["board"])

    spymasters = [a for a in assignments.values() if a["role"] == "spymaster"]
    assert len(spymasters) == 2
    for spymaster in spymasters:
        assert len(spymaster["colors"]) == 25
    guessers = [a for a in assignments.values() if a["role"] == "guesser"]
    for guesser in guessers:
        assert guesser["colors"] is None


def test_start_game_with_too_few_players_is_rejected(isolated_manager):
    room, host_id = _create_room(isolated_manager)

    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "start_game"})
        response = socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "not_enough_players"


def test_non_host_cannot_start_game(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"Player{i}")[1] for i in range(3)]

    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "start_game"})
        response = socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "permission_denied"


def test_give_clue_broadcasts_to_room(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"Player{i}")[1] for i in range(3)]

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
            host_socket.receive_json()
            g0.receive_json(); host_socket.receive_json()
            g1.receive_json(); host_socket.receive_json(); g0.receive_json()
            g2.receive_json(); host_socket.receive_json(); g0.receive_json(); g1.receive_json()

            sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
            assignments, room_state = _start_game_and_collect_assignments(host_socket, sockets)
            current_team = room_state["room"]["game_state"]["current_team"]

            spymaster_id = next(pid for pid, a in assignments.items() if a["team"] == current_team and a["role"] == "spymaster")
            spymaster_socket = sockets[spymaster_id]

            spymaster_socket.send_json({"type": "give_clue", "word": "ANIMAL", "number": 2})
            clue_events = [socket.receive_json() for socket in sockets.values()]
            room_updates = [socket.receive_json() for socket in sockets.values()]

    for event in clue_events:
        assert event["type"] == "clue_given"
        assert event["word"] == "ANIMAL"
        assert event["number"] == 2
    for update in room_updates:
        assert update["room"]["game_state"]["current_clue"]["word"] == "ANIMAL"


def test_make_guess_reveals_a_card_to_everyone(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"Player{i}")[1] for i in range(3)]

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
            host_socket.receive_json()
            g0.receive_json(); host_socket.receive_json()
            g1.receive_json(); host_socket.receive_json(); g0.receive_json()
            g2.receive_json(); host_socket.receive_json(); g0.receive_json(); g1.receive_json()

            sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
            assignments, room_state = _start_game_and_collect_assignments(host_socket, sockets)
            current_team = room_state["room"]["game_state"]["current_team"]

            spymaster_id = next(pid for pid, a in assignments.items() if a["team"] == current_team and a["role"] == "spymaster")
            guesser_id = next(pid for pid, a in assignments.items() if a["team"] == current_team and a["role"] == "guesser")

            sockets[spymaster_id].send_json({"type": "give_clue", "word": "ANIMAL", "number": 1})
            for socket in sockets.values():
                socket.receive_json()  # clue_given
                socket.receive_json()  # room_state

            sockets[guesser_id].send_json({"type": "make_guess", "card_index": 0})
            reveal_events = [socket.receive_json() for socket in sockets.values()]
            room_updates = [socket.receive_json() for socket in sockets.values()]

    for event in reveal_events:
        assert event["type"] == "card_revealed"
        assert event["card_index"] == 0
        assert event["guessed_by"] == guesser_id
    for update in room_updates:
        assert update["room"]["game_state"]["board"][0]["revealed"] is True


def test_reconnect_after_start_resends_own_assignment(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    guest_ids = [_join_room(isolated_manager, room.code, display_name=f"Player{i}")[1] for i in range(3)]

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[0]}") as g0, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[1]}") as g1, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_ids[2]}") as g2:
            host_socket.receive_json()
            g0.receive_json(); host_socket.receive_json()
            g1.receive_json(); host_socket.receive_json(); g0.receive_json()
            g2.receive_json(); host_socket.receive_json(); g0.receive_json(); g1.receive_json()

            sockets = {host_id: host_socket, guest_ids[0]: g0, guest_ids[1]: g1, guest_ids[2]: g2}
            assignments, _ = _start_game_and_collect_assignments(host_socket, sockets)

        first_assignment = assignments[host_id]

        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
            reconnect_room_state = socket.receive_json()
            reconnect_team_assigned = socket.receive_json()
            if first_assignment["role"] == "spymaster":
                reconnect_spymaster_view = socket.receive_json()
                assert reconnect_spymaster_view["type"] == "spymaster_view"
                assert reconnect_spymaster_view["colors"] == first_assignment["colors"]

    assert reconnect_room_state["type"] == "room_state"
    assert reconnect_team_assigned["type"] == "team_assigned"
    assert reconnect_team_assigned["team"] == first_assignment["team"]
    assert reconnect_team_assigned["role"] == first_assignment["role"]


def test_give_clue_before_start_is_rejected(isolated_manager):
    room, host_id = _create_room(isolated_manager)

    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "give_clue", "word": "ANIMAL", "number": 1})
        response = socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "game_not_started"
