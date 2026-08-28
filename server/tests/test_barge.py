import pytest

from twilio_observe.session_store import store


@pytest.mark.asyncio
async def test_barge_initiate(client):
    store._sessions.clear()
    store.create("CA333", "+15553333333")
    resp = await client.post("/api/barge/initiate", json={"callSid": "CA333"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "barged"
    session = store.get("CA333")
    assert session.status == "barged"


@pytest.mark.asyncio
async def test_barge_hand_back(client):
    store._sessions.clear()
    store.create("CA333", "+15553333333")
    session = store.get("CA333")
    session.status = "barged"
    resp = await client.post("/api/barge/hand-back", json={"callSid": "CA333"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "hand_back_complete"
    assert session.status == "active"


@pytest.mark.asyncio
async def test_barge_unknown_session(client):
    store._sessions.clear()
    resp = await client.post("/api/barge/initiate", json={"callSid": "NOPE"})
    assert resp.status_code == 404
