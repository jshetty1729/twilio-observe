import pytest

from twilio_observe.session_store import store


@pytest.mark.asyncio
async def test_coach_success(client):
    store._sessions.clear()
    store.create("CA222", "+15552222222")
    resp = await client.post("/api/coach", json={"callSid": "CA222", "instruction": "Ask about mileage"})
    assert resp.status_code == 200
    # When AI is idle and no WebSocket, coach fires immediately but can't send
    assert resp.json()["status"] == "delivered_no_ws"
    session = store.get("CA222")
    assert session.status == "coached"
    assert "Ask about mileage" in session.coaching_instructions


@pytest.mark.asyncio
async def test_coach_missing_call_sid(client):
    resp = await client.post("/api/coach", json={"instruction": "test"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_coach_unknown_session(client):
    store._sessions.clear()
    resp = await client.post("/api/coach", json={"callSid": "UNKNOWN", "instruction": "test"})
    assert resp.status_code == 404
