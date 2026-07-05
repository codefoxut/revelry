import asyncio
import time

import pytest
from fastapi.testclient import TestClient

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

_FAST_DURATION_SECONDS = 0.05


def test_schedule_fires_callback_once_after_the_duration():
    manager = NightTimerManager(duration_seconds=_FAST_DURATION_SECONDS)
    calls = []

    async def run():
        manager.schedule("ROOM1", lambda: _record(calls))
        await asyncio.sleep(_FAST_DURATION_SECONDS * 6)

    asyncio.run(run())
    assert calls == ["ROOM1"]


def test_cancel_prevents_the_callback_from_firing():
    manager = NightTimerManager(duration_seconds=_FAST_DURATION_SECONDS)
    calls = []

    async def run():
        manager.schedule("ROOM1", lambda: _record(calls))
        manager.cancel("ROOM1")
        await asyncio.sleep(_FAST_DURATION_SECONDS * 6)

    asyncio.run(run())
    assert calls == []


def test_rescheduling_replaces_the_pending_task():
    manager = NightTimerManager(duration_seconds=_FAST_DURATION_SECONDS)
    calls = []

    async def run():
        manager.schedule("ROOM1", lambda: _record(calls, "first"))
        manager.schedule("ROOM1", lambda: _record(calls, "second"))
        await asyncio.sleep(_FAST_DURATION_SECONDS * 6)

    asyncio.run(run())
    assert calls == ["second"]


def test_cancel_all_prevents_every_pending_callback():
    manager = NightTimerManager(duration_seconds=_FAST_DURATION_SECONDS)
    calls = []

    async def run():
        manager.schedule("ROOM1", lambda: _record(calls, "a"))
        manager.schedule("ROOM2", lambda: _record(calls, "b"))
        manager.cancel_all()
        await asyncio.sleep(_FAST_DURATION_SECONDS * 6)

    asyncio.run(run())
    assert calls == []


async def _record(calls: list, value: str = "ROOM1") -> None:
    calls.append(value)


@pytest.fixture
def isolated_manager():
    test_manager = RoomManager(RoomStore(InMemoryStore()))
    test_connections = ConnectionManager()
    test_sessions = GameSessionManager(test_manager, GameEngineStore(InMemoryStore()))
    test_night_timer = NightTimerManager(duration_seconds=_FAST_DURATION_SECONDS)
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
    return asyncio.run(manager.create_room(game_type="mafia", host_display_name="Alice"))


def _join_room(manager: RoomManager, code: str, display_name: str = "Bob"):
    return asyncio.run(manager.join_room(code, display_name=display_name))


def test_starting_a_game_broadcasts_a_night_timer_started_event(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    for i in range(3):
        _join_room(isolated_manager, room.code, display_name=f"Player{i}")
    client = TestClient(app)

    with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
        socket.receive_json()  # initial room_state
        socket.send_json({"type": "start_game"})
        socket.receive_json()  # role_assigned
        socket.receive_json()  # room_state
        timer_event = socket.receive_json()

    assert timer_event["type"] == "night_timer_started"
    assert timer_event["duration_seconds"] == _FAST_DURATION_SECONDS


def test_night_auto_resolves_when_the_timer_expires(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    for i in range(3):
        _join_room(isolated_manager, room.code, display_name=f"Player{i}")
    client = TestClient(app)

    with client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
            socket.receive_json()  # initial room_state
            socket.send_json({"type": "start_game"})
            socket.receive_json()  # role_assigned
            socket.receive_json()  # room_state (night)
            socket.receive_json()  # night_timer_started

            time.sleep(_FAST_DURATION_SECONDS * 6)  # long enough for the timer to fire

            night_result = socket.receive_json()
            # No mafia locked a target, so the timer's auto-advance resolves
            # night 1 via the default KILL_ANY fallback — an unseeded RNG
            # means the room_state that follows may or may not be preceded
            # by a game_over (e.g. if the random victim was the sole mafia
            # reaching immediate town victory), so just drain to room_state.
            update = socket.receive_json()
            if update["type"] != "room_state":
                update = socket.receive_json()

    assert night_result["type"] == "night_result"
    assert update["type"] == "room_state"
    assert update["room"]["game_state"]["phase"] in {"day", "game_over"}


def test_manually_advancing_before_the_timer_fires_cancels_it(isolated_manager):
    room, host_id = _create_room(isolated_manager)
    for i in range(3):
        _join_room(isolated_manager, room.code, display_name=f"Player{i}")
    client = TestClient(app)

    with client:
        with client.websocket_connect(f"/ws/{room.code}?player_id={host_id}") as socket:
            socket.receive_json()  # initial room_state
            socket.send_json({"type": "start_game"})
            socket.receive_json()  # role_assigned
            socket.receive_json()  # room_state (night)
            socket.receive_json()  # night_timer_started

            socket.send_json({"type": "advance_phase"})
            socket.receive_json()  # night_result
            # An unseeded RNG means the default KILL_ANY fallback could kill
            # the sole mafia and end the game immediately — in that case a
            # game_over broadcast lands before room_state, so drain to it.
            update = socket.receive_json()
            if update["type"] != "room_state":
                socket.receive_json()  # room_state

            # If the (now-cancelled) night timer had still fired, it would
            # have tried to auto-advance a second time — confirm the socket
            # stays quiet instead.
            socket.send_json({"type": "ping"})
            pong = socket.receive_json()

    assert pong["type"] == "pong"
