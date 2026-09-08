import sys
from pathlib import Path

from httpx2 import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app, delete_session  # noqa: E402


async def _client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_categories_include_mixed_option() -> None:
    async with await _client() as client:
        response = await client.get("/categories")
    assert response.status_code == 200
    ids = {c["id"] for c in response.json()}
    assert "mixed" in ids
    assert "classical" in ids


async def test_start_requires_at_least_two_teams() -> None:
    async with await _client() as client:
        response = await client.post(
            "/start",
            json={"session_id": "test-min-teams", "teams": ["Solo"]},
        )
    assert response.status_code == 400
    delete_session("test-min-teams")


async def test_reveal_returns_a_note_sequence() -> None:
    session_id = "test-reveal"
    async with await _client() as client:
        await client.post(
            "/start",
            json={"session_id": session_id, "teams": ["Red", "Blue"], "category": "classical"},
        )
        reveal = await client.post(f"/reveal/{session_id}")
        assert reveal.status_code == 200
        current = reveal.json()["current"]
        assert current["title"]
        assert len(current["notes"]) > 0
        assert len(current["notes"][0]) == 2

    delete_session(session_id)


async def test_full_round_correct_then_steal() -> None:
    session_id = "test-round-cycle"
    async with await _client() as client:
        start = await client.post(
            "/start",
            json={"session_id": session_id, "teams": ["Red", "Blue"], "category": "classical"},
        )
        assert start.status_code == 200
        state = start.json()
        assert state["scores"] == {"t0": 0, "t1": 0}

        await client.post(f"/reveal/{session_id}")
        correct = await client.post(f"/resolve/{session_id}", json={"result": "correct"})
        state = correct.json()
        assert state["scores"]["t0"] == 1
        assert state["turn_index"] == 1
        assert state["current"] is None

        await client.post(f"/reveal/{session_id}")
        passed = await client.post(f"/resolve/{session_id}", json={"result": "pass"})
        assert passed.json()["pending_steal"] is True

        stolen = await client.post(f"/resolve/{session_id}", json={"result": "steal_correct"})
        state = stolen.json()
        assert state["scores"]["t0"] == 2
        assert state["pending_steal"] is False

    delete_session(session_id)


async def test_reveal_fails_when_tune_already_current() -> None:
    session_id = "test-double-reveal"
    async with await _client() as client:
        await client.post(
            "/start",
            json={"session_id": session_id, "teams": ["Red", "Blue"], "category": "classical"},
        )
        await client.post(f"/reveal/{session_id}")
        second = await client.post(f"/reveal/{session_id}")
        assert second.status_code == 400

    delete_session(session_id)
