import sys
from pathlib import Path

from httpx2 import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app, delete_session  # noqa: E402


async def _client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_config_reports_online_availability() -> None:
    async with await _client() as client:
        response = await client.get("/config")
    assert response.status_code == 200
    assert "online_mode_available" in response.json()


async def test_categories_include_mixed_option() -> None:
    async with await _client() as client:
        response = await client.get("/categories")
    assert response.status_code == 200
    categories = response.json()["categories"]
    ids = {c["id"] for c in categories}
    assert "mixed" in ids
    assert "animals" in ids


async def test_start_requires_at_least_two_teams() -> None:
    async with await _client() as client:
        response = await client.post(
            "/start",
            json={"session_id": "test-min-teams", "teams": ["Solo"]},
        )
    assert response.status_code == 400
    delete_session("test-min-teams")


async def test_full_turn_cycle_awards_points_and_advances_turn() -> None:
    session_id = "test-turn-cycle"
    async with await _client() as client:
        start = await client.post(
            "/start",
            json={
                "session_id": session_id,
                "teams": ["Red", "Blue"],
                "category_id": "animals",
                "round_seconds": 45,
                "target_score": 5,
            },
        )
        assert start.status_code == 200
        state = start.json()
        assert state["turn_index"] == 0
        assert state["scores"] == {"t0": 0, "t1": 0}

        deck = await client.post(f"/deck/{session_id}", json={"count": 10})
        assert deck.status_code == 200
        words = deck.json()["words"]
        assert 5 <= len(words) <= 10

        resolved = await client.post(
            f"/resolve/{session_id}",
            json={"correct": words[:3], "passed": words[3:5]},
        )
        assert resolved.status_code == 200
        state = resolved.json()
        assert state["scores"]["t0"] == 3
        assert state["turn_index"] == 1
        assert set(words[:5]).issubset(set(state["used_words"]))

    delete_session(session_id)


async def test_game_ends_when_target_score_reached() -> None:
    session_id = "test-game-over"
    async with await _client() as client:
        await client.post(
            "/start",
            json={
                "session_id": session_id,
                "teams": ["Red", "Blue"],
                "category_id": "animals",
                "target_score": 2,
            },
        )
        resolved = await client.post(
            f"/resolve/{session_id}",
            json={"correct": ["Elephant", "Kangaroo"], "passed": []},
        )
        state = resolved.json()
        assert state["game_over"] is True
        assert state["winner_id"] == "t0"

    delete_session(session_id)
