from httpx2 import ASGITransport, AsyncClient

from app.main import app


async def _client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_get_game_info_returns_full_payload():
    async with await _client() as client:
        response = await client.get("/api/game-info")

    assert response.status_code == 200
    body = response.json()
    assert len(body["roles"]) == 16
    assert len(body["phases"]) == 4
    assert len(body["tie_breakers"]) == 2
    assert len(body["rules"]) > 0
    assert len(body["faq"]) > 0


async def test_get_game_info_reflects_mutual_exclusion_pairs():
    async with await _client() as client:
        response = await client.get("/api/game-info")

    roles_by_key = {role["key"]: role for role in response.json()["roles"]}
    assert roles_by_key["oracle"]["mutually_exclusive_with"] == ["detective"]
    assert roles_by_key["detective"]["mutually_exclusive_with"] == ["oracle"]
    assert roles_by_key["hypnotizer"]["mutually_exclusive_with"] == ["escort"]
    assert roles_by_key["escort"]["mutually_exclusive_with"] == ["hypnotizer"]
    assert roles_by_key["villager"]["mutually_exclusive_with"] == []


async def test_get_game_info_role_fields_match_registry():
    async with await _client() as client:
        response = await client.get("/api/game-info")

    roles_by_key = {role["key"]: role for role in response.json()["roles"]}
    vigilante = roles_by_key["vigilante"]
    assert vigilante["max_uses"] == 2
    assert vigilante["acts_at_night"] is True
    assert vigilante["allow_self_target"] is False

    serial_killer = roles_by_key["serial_killer"]
    assert serial_killer["hostile"] is True
