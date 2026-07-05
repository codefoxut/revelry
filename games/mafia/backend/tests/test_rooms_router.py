import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.platform.room import RoomPhase
from app.platform.room_manager import RoomManager
from app.platform.stores.in_memory import InMemoryStore
from app.platform.stores.room_store import RoomStore
from app.routers.rooms import get_room_manager


@pytest.fixture(autouse=True)
def isolated_room_manager():
    """Each test gets a fresh in-memory RoomStore so room codes/state from
    one test can't leak into another via the module-level singleton.
    """
    test_manager = RoomManager(RoomStore(InMemoryStore()))
    app.dependency_overrides[get_room_manager] = lambda: test_manager
    yield
    app.dependency_overrides.pop(get_room_manager, None)


async def _client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_create_room_returns_host_player_id():
    async with await _client() as client:
        response = await client.post(
            "/api/rooms",
            json={"game_type": "mafia", "host_display_name": "Alice"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["room"]["game_type"] == "mafia"
    assert len(body["room"]["players"]) == 1
    assert body["room"]["players"][0]["id"] == body["player_id"]
    assert body["room"]["invite_url"].endswith(f"/room/{body['room']['code']}")


async def test_get_room_summary_hides_player_identities():
    async with await _client() as client:
        created = await client.post(
            "/api/rooms",
            json={"game_type": "mafia", "host_display_name": "Alice"},
        )
        code = created.json()["room"]["code"]

        response = await client.get(f"/api/rooms/{code}")

    assert response.status_code == 200
    body = response.json()
    assert body["player_count"] == 1
    assert "players" not in body


async def test_get_unknown_room_returns_404():
    async with await _client() as client:
        response = await client.get("/api/rooms/ZZZZZ")

    assert response.status_code == 404


async def test_join_room_adds_second_player():
    async with await _client() as client:
        created = await client.post(
            "/api/rooms",
            json={"game_type": "mafia", "host_display_name": "Alice"},
        )
        code = created.json()["room"]["code"]

        response = await client.post(
            f"/api/rooms/{code}/join",
            json={"display_name": "Bob"},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["room"]["players"]) == 2
    assert body["room"]["players"][1]["id"] == body["player_id"]


async def test_join_unknown_room_returns_404():
    async with await _client() as client:
        response = await client.post(
            "/api/rooms/ZZZZZ/join",
            json={"display_name": "Bob"},
        )

    assert response.status_code == 404


async def test_join_full_room_returns_409():
    async with await _client() as client:
        created = await client.post(
            "/api/rooms",
            json={"game_type": "mafia", "host_display_name": "Alice"},
        )
        code = created.json()["room"]["code"]

        # A fresh room defaults to a max of 20 players, so drive it full via
        # the manager directly rather than joining 20 times over HTTP.
        test_manager = app.dependency_overrides[get_room_manager]()
        room = await test_manager.get_room(code)
        room.max_players = 1

        response = await client.post(
            f"/api/rooms/{code}/join",
            json={"display_name": "Bob"},
        )

    assert response.status_code == 409


async def test_create_and_join_persist_avatar():
    async with await _client() as client:
        created = await client.post(
            "/api/rooms",
            json={"game_type": "mafia", "host_display_name": "Alice", "host_avatar": "fox"},
        )
        code = created.json()["room"]["code"]

        joined = await client.post(
            f"/api/rooms/{code}/join",
            json={"display_name": "Bob", "avatar": "owl"},
        )

    host_player = created.json()["room"]["players"][0]
    guest_player = joined.json()["room"]["players"][1]
    assert host_player["avatar"] == "fox"
    assert guest_player["avatar"] == "owl"


async def test_join_in_progress_room_via_rest_is_spectator():
    async with await _client() as client:
        created = await client.post(
            "/api/rooms",
            json={"game_type": "mafia", "host_display_name": "Alice"},
        )
        code = created.json()["room"]["code"]

        test_manager = app.dependency_overrides[get_room_manager]()
        room = await test_manager.get_room(code)
        room.phase = RoomPhase.IN_GAME

        joined = await client.post(
            f"/api/rooms/{code}/join",
            json={"display_name": "Latecomer"},
        )

    assert joined.status_code == 200
    latecomer = joined.json()["room"]["players"][-1]
    assert latecomer["is_spectator"] is True
