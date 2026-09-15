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
    return asyncio.run(manager.create_room(game_type="trivia_showdown", host_display_name="Host"))


def _join_room(manager: RoomManager, code: str, display_name: str = "Bob"):
    return asyncio.run(manager.join_room(code, display_name=display_name))


def test_connect_receives_initial_room_state(isolated_manager):
    room, host_id = _create_room(isolated_manager)

    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        event = socket.receive_json()

    assert event["type"] == "room_state"
    assert event["room"]["code"] == room.code
    assert event["room"]["players"][0]["id"] == host_id


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


def test_non_host_kick_is_rejected(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)

    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
        guest_socket.receive_json()  # initial room_state
        guest_socket.send_json({"type": "kick_player", "target_player_id": host_id})
        response = guest_socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "permission_denied"


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
    _, guest_id = _join_room(isolated_manager, room.code)

    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "start_game"})
        response = socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "permission_denied"


def _start_game_and_drain(host_socket, sockets: dict):
    """Sends start_game from the host and drains, for every connected
    socket (including the host's own), the shared question_shown broadcast
    followed by the shared room_state broadcast. Unlike Codenames there's no
    private per-player assignment to drain first — every event here is
    public.
    """
    host_socket.send_json({"type": "start_game"})

    question_events = {}
    room_state = None
    for player_id, socket in sockets.items():
        question_events[player_id] = socket.receive_json()
        room_state = socket.receive_json()
    return question_events, room_state


def test_start_game_with_enough_players_opens_the_first_question(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
            host_socket.receive_json()  # own initial room_state
            guest_socket.receive_json()  # guest's own initial room_state
            host_socket.receive_json()  # presence: guest joined

            sockets = {host_id: host_socket, guest_id: guest_socket}
            question_events, room_state = _start_game_and_drain(host_socket, sockets)

    for event in question_events.values():
        assert event["type"] == "question_shown"
        assert event["question_number"] == 1

    assert room_state["type"] == "room_state"
    assert room_state["room"]["phase"] == "in_game"
    game_state = room_state["room"]["game_state"]
    assert game_state["phase"] == "question_open"
    assert game_state["scores"] == {guest_id: 0}


def test_buzz_in_locks_the_question_for_the_host_to_judge(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
            host_socket.receive_json()
            guest_socket.receive_json()
            host_socket.receive_json()

            sockets = {host_id: host_socket, guest_id: guest_socket}
            _start_game_and_drain(host_socket, sockets)

            guest_socket.send_json({"type": "buzz_in"})
            buzzed_events = [socket.receive_json() for socket in sockets.values()]
            room_updates = [socket.receive_json() for socket in sockets.values()]

    for event in buzzed_events:
        assert event["type"] == "player_buzzed"
        assert event["player_id"] == guest_id
    for update in room_updates:
        assert update["room"]["game_state"]["phase"] == "answering"
        assert update["room"]["game_state"]["buzzed_player_id"] == guest_id


def test_host_only_can_judge_the_buzzed_in_answer(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
            host_socket.receive_json()
            guest_socket.receive_json()
            host_socket.receive_json()

            sockets = {host_id: host_socket, guest_id: guest_socket}
            _start_game_and_drain(host_socket, sockets)

            guest_socket.send_json({"type": "buzz_in"})
            for socket in sockets.values():
                socket.receive_json()  # player_buzzed
                socket.receive_json()  # room_state

            guest_socket.send_json({"type": "judge_answer", "correct": True})
            error = guest_socket.receive_json()

            host_socket.send_json({"type": "judge_answer", "correct": True})
            judged_events = [socket.receive_json() for socket in sockets.values()]
            revealed_events = [socket.receive_json() for socket in sockets.values()]
            room_updates = [socket.receive_json() for socket in sockets.values()]

    assert error["type"] == "error"
    assert error["code"] == "permission_denied"

    for event in judged_events:
        assert event["type"] == "answer_judged"
        assert event["player_id"] == guest_id
        assert event["correct"] is True
        assert event["score_delta"] == 100
    for event in revealed_events:
        assert event["type"] == "answer_revealed"
    for update in room_updates:
        assert update["room"]["game_state"]["phase"] == "revealed"
        assert update["room"]["game_state"]["scores"][guest_id] == 100


def test_next_question_advances_and_final_one_ends_the_game(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    _, guest_id = _join_room(isolated_manager, room.code)

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_socket, \
             client.websocket_connect(f"/ws/{room.code}?player_id={guest_id}") as guest_socket:
            host_socket.receive_json()
            guest_socket.receive_json()
            host_socket.receive_json()

            sockets = {host_id: host_socket, guest_id: guest_socket}
            _, room_state = _start_game_and_drain(host_socket, sockets)
            total_questions = room_state["room"]["game_state"]["total_questions"]

            host_socket.send_json({"type": "reveal"})
            for socket in sockets.values():
                socket.receive_json()  # answer_revealed
                socket.receive_json()  # room_state

            for _ in range(total_questions - 1):
                host_socket.send_json({"type": "next_question"})
                for socket in sockets.values():
                    socket.receive_json()  # question_shown
                    socket.receive_json()  # room_state

                host_socket.send_json({"type": "reveal"})
                for socket in sockets.values():
                    socket.receive_json()  # answer_revealed
                    socket.receive_json()  # room_state

            host_socket.send_json({"type": "next_question"})
            game_over_events = [socket.receive_json() for socket in sockets.values()]
            final_updates = [socket.receive_json() for socket in sockets.values()]

    for event in game_over_events:
        assert event["type"] == "game_over"
    for update in final_updates:
        assert update["room"]["game_state"]["phase"] == "game_over"


def test_reveal_before_start_is_rejected(isolated_manager):
    room, host_id = _create_room(isolated_manager)

    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "reveal"})
        response = socket.receive_json()

    assert response["type"] == "error"
    assert response["code"] == "game_not_started"
