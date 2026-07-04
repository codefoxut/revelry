import pytest

from app.platform.exceptions import PermissionDeniedError, RoomFullError, RoomNotFoundError
from app.platform.room import RoomPhase
from app.platform.room_manager import RoomManager
from app.platform.stores.in_memory import InMemoryStore
from app.platform.stores.room_store import RoomStore


@pytest.fixture
def manager() -> RoomManager:
    return RoomManager(RoomStore(InMemoryStore()))


async def test_create_room_makes_host_the_only_player(manager: RoomManager):
    room, host_id = await manager.create_room("mafia", "Alice")

    assert len(room.code) == 5
    assert room.host_player_id == host_id
    assert room.players[host_id].is_host is True
    assert room.active_player_count == 1


async def test_join_room_adds_player(manager: RoomManager):
    room, _ = await manager.create_room("mafia", "Alice")

    room, player_id = await manager.join_room(room.code, "Bob")

    assert room.active_player_count == 2
    assert room.players[player_id].is_host is False
    assert room.players[player_id].is_spectator is False


async def test_join_unknown_room_raises(manager: RoomManager):
    with pytest.raises(RoomNotFoundError):
        await manager.join_room("ZZZZZ", "Ghost")


async def test_join_full_room_raises(manager: RoomManager):
    room, _ = await manager.create_room("mafia", "Host")
    room.max_players = 1

    with pytest.raises(RoomFullError):
        await manager.join_room(room.code, "Latecomer")


async def test_join_in_progress_game_forces_spectator(manager: RoomManager):
    room, _ = await manager.create_room("mafia", "Host")
    room.phase = RoomPhase.IN_GAME

    room, player_id = await manager.join_room(room.code, "Latecomer")

    assert room.players[player_id].is_spectator is True


async def test_leave_room_migrates_host(manager: RoomManager):
    room, host_id = await manager.create_room("mafia", "Alice")
    room, bob_id = await manager.join_room(room.code, "Bob")

    room = await manager.leave_room(room.code, host_id)

    assert room is not None
    assert room.host_player_id == bob_id
    assert room.players[bob_id].is_host is True


async def test_leave_room_deletes_empty_room(manager: RoomManager):
    room, host_id = await manager.create_room("mafia", "Alice")

    result = await manager.leave_room(room.code, host_id)

    assert result is None
    assert await manager.get_room(room.code) is None


async def test_kick_player_requires_host(manager: RoomManager):
    room, host_id = await manager.create_room("mafia", "Alice")
    room, bob_id = await manager.join_room(room.code, "Bob")
    room, carol_id = await manager.join_room(room.code, "Carol")

    with pytest.raises(PermissionDeniedError):
        await manager.kick_player(room.code, bob_id, carol_id)

    room = await manager.kick_player(room.code, host_id, bob_id)
    assert bob_id not in room.players


async def test_host_cannot_kick_self(manager: RoomManager):
    room, host_id = await manager.create_room("mafia", "Alice")

    with pytest.raises(PermissionDeniedError):
        await manager.kick_player(room.code, host_id, host_id)


def test_build_invite_url_contains_code(manager: RoomManager):
    url = manager.build_invite_url("ABCDE")
    assert url.endswith("/room/ABCDE")
