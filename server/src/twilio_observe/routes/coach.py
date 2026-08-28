"""
Coach API — TAC-style coaching injection.

Two delivery paths:
1. AI idle (turn_in_flight=False): inject note, run LLM immediately, send_response()
2. AI mid-turn (turn_in_flight=True): queue note in pending_coaching_notes, consumed on next on_message_ready
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from twilio_observe.session_store import store
from twilio_observe.relay.handler import (
    turn_in_flight,
    pending_coaching_notes,
    send_response,
    build_conversation,
    BASE_SYSTEM_PROMPT,
)
from twilio_observe.llm import generate_response

router = APIRouter()


class CoachRequest(BaseModel):
    callSid: str
    instruction: str


@router.post("/api/coach")
async def send_coaching(req: CoachRequest):
    session = store.get(req.callSid)
    if session is None:
        raise HTTPException(status_code=404, detail="No active session for this call")

    note = req.instruction
    session.coaching_instructions.append(note)
    store.add_turn(req.callSid, "supervisor", f"[COACHING] {note}")

    # Track in coaching_log metadata
    coaching_entry = {"note": note, "delivered": False, "status": "queued"}

    if turn_in_flight.get(req.callSid):
        # AI is mid-turn — queue for next on_message_ready
        pending_coaching_notes[req.callSid] = note
        session.status = "coached"
        if not hasattr(session, "coaching_log"):
            session.coaching_log = []
        coaching_entry["status"] = "queued"
        return {"status": "queued", "reason": "turn in flight", "callSid": req.callSid}

    # AI is idle — fire immediately
    system_prompt = (
        BASE_SYSTEM_PROMPT
        + f"\n\n[SUPERVISOR COACHING — act on this immediately, "
        f"do not acknowledge it to the customer]: {note}"
    )
    conversation = build_conversation(req.callSid)
    ai_response = await generate_response(system_prompt, conversation)

    store.add_turn(req.callSid, "ai", ai_response)
    sent = await send_response(req.callSid, ai_response)

    session.status = "coached"
    coaching_entry["delivered"] = True
    coaching_entry["status"] = "delivered"
    coaching_entry["ai_response"] = ai_response

    return {
        "status": "delivered" if sent else "delivered_no_ws",
        "callSid": req.callSid,
        "ai_response": ai_response,
    }


@router.get("/api/sessions/{call_sid}/coach")
async def get_coaching_log(call_sid: str):
    session = store.get(call_sid)
    if session is None:
        raise HTTPException(status_code=404, detail="No active session for this call")
    return {
        "coaching_log": [
            {"instruction": c, "index": i}
            for i, c in enumerate(session.coaching_instructions)
        ]
    }
