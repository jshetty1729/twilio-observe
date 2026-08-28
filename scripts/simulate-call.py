#!/usr/bin/env python3
"""
Simulates the Camping World demo call for testing the supervisor dashboard
without needing real Twilio credentials or a phone call.

Usage: python scripts/simulate-call.py

Connects via WebSocket to the local server and simulates the
ConversationRelay protocol.
"""

import asyncio
import json
import time

import websockets

SERVER_URL = "ws://localhost:8000"
CALL_SID = f"CA{int(time.time())}sim"

DEMO_SCRIPT = [
    {
        "delay": 1.0,
        "message": {
            "type": "setup",
            "sessionId": f"VX{CALL_SID}",
            "callSid": CALL_SID,
            "from": "+15551234567",
            "to": "+15559876543",
            "direction": "inbound",
            "callStatus": "RINGING",
            "customParameters": {},
        },
        "description": "Call connected",
    },
    {
        "delay": 3.0,
        "message": {
            "type": "prompt",
            "voicePrompt": "I've got a 2017 Keystone Cougar. What kind of trade-in value am I looking at toward a Montana High Country?",
            "lang": "en-US",
            "last": True,
        },
        "description": "Customer asks about trade-in value",
    },
    {
        "delay": 8.0,
        "message": {
            "type": "prompt",
            "voicePrompt": "About 34,000 miles, very good condition. We've kept it well maintained.",
            "lang": "en-US",
            "last": True,
        },
        "description": "Customer provides vehicle details",
    },
    {
        "delay": 12.0,
        "message": {
            "type": "prompt",
            "voicePrompt": "Yeah, that sounds good. I'm thinking Saturday.",
            "lang": "en-US",
            "last": True,
        },
        "description": "Customer wants to schedule (positive)",
    },
    {
        "delay": 18.0,
        "message": {
            "type": "prompt",
            "voicePrompt": "3 to 5 business days? I just said I want to come Saturday. That's ridiculous.",
            "lang": "en-US",
            "last": True,
        },
        "description": "Customer frustrated (CSAT should drop)",
    },
    {
        "delay": 23.0,
        "message": {
            "type": "prompt",
            "voicePrompt": "That's ridiculous. I've been on this call for ten minutes and you can't just book a Saturday slot?",
            "lang": "en-US",
            "last": True,
        },
        "description": "Customer very frustrated - barge opportunity",
    },
]


async def main():
    print(f"\nSimulating Camping World demo call")
    print(f"   Call SID: {CALL_SID}")
    print(f"   Server: {SERVER_URL}")
    print(f"   Dashboard: http://localhost:5173\n")

    uri = f"{SERVER_URL}/ws/relay/{CALL_SID}"

    try:
        async with websockets.connect(uri) as ws:
            print("WebSocket connected to server\n")

            for step in DEMO_SCRIPT:
                await asyncio.sleep(step["delay"])
                print(f"  [{step['delay']:.0f}s] {step['description']}")
                if step["message"]["type"] == "prompt":
                    print(f"   Customer: \"{step['message']['voicePrompt']}\"")

                await ws.send(json.dumps(step["message"]))

                # Wait for AI response
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    msg = json.loads(response)
                    if msg.get("type") == "text":
                        token = msg.get("token", "")
                        preview = token[:80] + ("..." if len(token) > 80 else "")
                        print(f"   AI: \"{preview}\"\n")
                except asyncio.TimeoutError:
                    pass

            print("\nDemo script complete.")
            print("   The call remains active for you to test Coach and Barge.")
            print("   Open http://localhost:5173 and click on the active call.")
            print("   Press Ctrl+C to end.\n")

            # Keep connection alive
            await asyncio.Future()

    except ConnectionRefusedError:
        print("WebSocket error: Connection refused")
        print("   Make sure the server is running: make server")
    except KeyboardInterrupt:
        print("\nClosing...")


if __name__ == "__main__":
    asyncio.run(main())
