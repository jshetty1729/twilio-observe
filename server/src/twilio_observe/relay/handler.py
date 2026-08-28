"""
ConversationRelay WebSocket handler.

Implements the TAC on_message_ready pattern:
- turn_in_flight flag per session (enables immediate vs queued coaching)
- barge_active flag per session (suppresses AI TTS when supervisor has the call)
- pending_coaching_notes consumption before LLM run
- CSAT heuristic scoring after each turn
"""

from __future__ import annotations

import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from twilio_observe.session_store import store
from twilio_observe.csat import csat_scorer
from twilio_observe.llm import generate_response, BASE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Topic detection signals (lightweight heuristic — CI operators provide authoritative version)
HIGH_VALUE_SIGNALS = [
    "trade-in", "trade in", "montana", "keystone", "cougar", "grand design",
    "financing", "finance", "purchase", "buy", "appraisal", "deposit",
]

# TAC-style per-session state
turn_in_flight: dict[str, bool] = {}
pending_coaching_notes: dict[str, str] = {}
barge_active: dict[str, bool] = {}

# Store active WebSocket connections for send_response
active_connections: dict[str, WebSocket] = {}


def get_effective_system_prompt(call_sid: str) -> str:
    session = store.get(call_sid)
    if session is None:
        return BASE_SYSTEM_PROMPT

    prompt = BASE_SYSTEM_PROMPT

    # Consume any pending coaching note (queued while turn was in flight)
    coaching_note = pending_coaching_notes.pop(call_sid, None)
    if coaching_note:
        prompt += (
            f"\n\n[SUPERVISOR COACHING — act on this immediately, "
            f"do not acknowledge it to the customer]: {coaching_note}"
        )
    elif session.coaching_instructions:
        latest = session.coaching_instructions[-1]
        prompt += (
            f"\n\n[SUPERVISOR COACHING — act on this immediately, "
            f"do not acknowledge it to the customer]: {latest}"
        )
    return prompt


def build_conversation(call_sid: str) -> list[dict[str, str]]:
    session = store.get(call_sid)
    if session is None:
        return []

    messages = []
    for turn in session.transcript:
        role = turn["role"]
        if role == "customer":
            messages.append({"role": "user", "content": turn["content"]})
        elif role == "ai":
            messages.append({"role": "assistant", "content": turn["content"]})
    return messages


async def send_response(call_sid: str, text: str) -> bool:
    """Send a response out-of-band (used for immediate coaching fire)."""
    ws = active_connections.get(call_sid)
    if ws is None:
        return False
    try:
        await ws.send_text(json.dumps({
            "type": "text",
            "token": text,
            "last": True,
        }))
        return True
    except Exception as e:
        logger.error(f"send_response failed for {call_sid}: {e}")
        return False


async def handle_relay_connection(ws: WebSocket, call_sid: str):
    await ws.accept()
    logger.info(f"ConversationRelay WebSocket connected: {call_sid}")

    session_call_sid = call_sid
    active_connections[call_sid] = ws

    try:
        while True:
            raw = await ws.receive_text()
            message = json.loads(raw)
            msg_type = message.get("type")

            if msg_type == "setup":
                session_call_sid = message.get("callSid", call_sid)
                caller = message.get("from", "unknown")
                # Update connection mapping with actual call SID
                if session_call_sid != call_sid:
                    active_connections[session_call_sid] = ws
                if store.get(session_call_sid) is None:
                    store.create(session_call_sid, caller)
                csat_scorer.init_call(session_call_sid)
                turn_in_flight[session_call_sid] = False
                logger.info(f"CR session setup: {session_call_sid} from {caller}")

            elif msg_type == "prompt":
                if not message.get("last"):
                    continue

                session = store.get(session_call_sid)
                if session is None:
                    logger.error(f"No session for prompt: {session_call_sid}")
                    continue

                # Barge suppression — AI stays silent, log turn only
                if barge_active.get(session_call_sid):
                    voice_prompt = message.get("voicePrompt", "")
                    store.add_turn(session_call_sid, "customer", voice_prompt)
                    logger.info(f"Barge active — AI suppressed for {session_call_sid}")
                    continue

                turn_in_flight[session_call_sid] = True

                voice_prompt = message.get("voicePrompt", "")
                store.add_turn(session_call_sid, "customer", voice_prompt)

                # Topic detection heuristic
                if not session.topic:
                    msg_lower = voice_prompt.lower()
                    if any(w in msg_lower for w in HIGH_VALUE_SIGNALS):
                        session.topic = "RV Trade-In — High Value"

                system_prompt = get_effective_system_prompt(session_call_sid)
                conversation = build_conversation(session_call_sid)
                ai_response = await generate_response(system_prompt, conversation)

                store.add_turn(session_call_sid, "ai", ai_response)

                prev_csat = session.csat
                csat_scorer.score_customer_message(session_call_sid, voice_prompt)
                csat_scorer.score_ai_response(session_call_sid, ai_response)
                session.csat = csat_scorer.get_score(session_call_sid)

                # Alert if CSAT dropped significantly
                if prev_csat >= 5 and session.csat < 5:
                    alert = "CSAT dropped below 5 — customer disengagement detected"
                    if alert not in session.alerts:
                        session.alerts.append(alert)
                if prev_csat >= 3 and session.csat <= 2:
                    alert = "Sales traction lost — at-risk of abandonment"
                    if alert not in session.alerts:
                        session.alerts.append(alert)

                await ws.send_text(json.dumps({
                    "type": "text",
                    "token": ai_response,
                    "last": True,
                }))

                turn_in_flight[session_call_sid] = False

            elif msg_type == "interrupt":
                utterance = message.get("utteranceUntilInterrupt", "")
                logger.info(f"Caller interrupted at: \"{utterance}\"")

            else:
                logger.info(f"Unhandled CR message type: {msg_type}")

    except WebSocketDisconnect:
        logger.info(f"ConversationRelay WebSocket closed: {session_call_sid}")
    except Exception as e:
        logger.error(f"WebSocket error for {session_call_sid}: {e}")
    finally:
        active_connections.pop(call_sid, None)
        active_connections.pop(session_call_sid, None)
        turn_in_flight.pop(session_call_sid, None)
