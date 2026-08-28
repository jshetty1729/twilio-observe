import json

import pytest

from twilio_observe.config import settings


@pytest.mark.asyncio
async def test_inbound_returns_twiml(client):
    settings.ngrok_url = "https://test.ngrok.io"
    resp = await client.post(
        "/api/calls/inbound",
        data={"CallSid": "CA999", "From": "+15559999999"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    assert "text/xml" in resp.headers["content-type"]
    body = resp.text
    assert "<ConversationRelay" in body
    assert "wss://test.ngrok.io/ws/relay/CA999" in body


@pytest.mark.asyncio
async def test_connect_action_barge(client):
    settings.ngrok_url = "https://test.ngrok.io"
    resp = await client.post(
        "/api/calls/connect-action",
        data={"CallSid": "CA999", "HandoffData": json.dumps({"reason": "barge"})},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert "<Conference" in body


@pytest.mark.asyncio
async def test_connect_action_hangup(client):
    resp = await client.post(
        "/api/calls/connect-action",
        data={"CallSid": "CA999", "HandoffData": ""},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert "<Hangup" in body
