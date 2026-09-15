"""WS integration tests for Would You Rather."""
from __future__ import annotations

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


def _create_room(manager):
    return asyncio.run(manager.create_room(game_type="would_you_rather", host_display_name="Host"))


def _join_room(manager, code: str, name: str = "Bob"):
    return asyncio.run(manager.join_room(code, display_name=name))


def test_connect_receives_initial_room_state(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as ws:
        event = ws.receive_json()
    assert event["type"] == "room_state"
    assert event["room"]["code"] == room.code


def test_ping_pong(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    with TestClient(app) as client, client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as ws:
        ws.receive_json()
        ws.send_json({"type": "ping"})
        resp = ws.receive_json()
    assert resp == {"type": "pong"}


def _drain_until(ws, event_type: str, max_events: int = 20) -> dict:
    """Drain events until we find one with the given type."""
    for _ in range(max_events):
        event = ws.receive_json()
        if event.get("type") == event_type:
            return event
    raise AssertionError(f"Did not receive {event_type!r} in {max_events} events")


def test_full_round(isolated_manager):
    """Host + 2 players: start game, vote, reveal, confirm votes."""
    room, host_id = _create_room(isolated_manager)
    _, p1_id = _join_room(isolated_manager, room.code, "Alice")

    with TestClient(app) as client:
        with (
            client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as host_ws,
            client.websocket_connect(f"/ws/{room.code}?player_id={p1_id}") as p1_ws,
        ):
            # host starts game (enough players since host also plays)
            _drain_until(host_ws, "room_state")
            _drain_until(p1_ws, "room_state")

            host_ws.send_json({"type": "start_game"})
            _drain_until(host_ws, "room_state")  # game started room_state

            # p1 votes
            p1_ws.send_json({"type": "submit_vote", "choice": "a"})
            _drain_until(host_ws, "room_state")  # after vote

            # host reveals → votes_revealed event
            host_ws.send_json({"type": "reveal"})
            votes_event = _drain_until(host_ws, "votes_revealed")
            assert p1_id in votes_event["votes"]
            assert votes_event["votes"][p1_id] == "a"
