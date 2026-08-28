import pytest

from twilio_observe.session_store import store


@pytest.mark.asyncio
async def test_get_sessions_empty(client):
    store._sessions.clear()
    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_sessions_returns_active(client):
    store._sessions.clear()
    store.create("CA111", "+15551111111")
    store.add_turn("CA111", "customer", "Hello")
    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["callSid"] == "CA111"
    assert data[0]["callerNumber"] == "+15551111111"
    assert data[0]["csat"] == 7
    assert data[0]["status"] == "active"
    assert len(data[0]["transcript"]) == 1
