"""
Sessions API — TAC-style session listing with metadata.

GET /api/sessions — all active sessions with CSAT, topic, alerts
GET /api/sessions/{call_sid}/messages — transcript for a specific session
GET /api/sessions/{call_sid}/context — full context including CI events + metadata
"""

from fastapi import APIRouter, HTTPException

from twilio_observe.session_store import store
from twilio_observe.csat import csat_scorer

router = APIRouter()


@router.get("/api/sessions")
async def get_sessions():
    sessions = store.get_all_active()
    return [
        {
            "callSid": s.call_sid,
            "callerNumber": s.caller_number,
            "startTime": int(s.start_time * 1000),
            "csat": s.csat,
            "topic": s.topic,
            "status": s.status,
            "transcript": s.transcript,
            "alerts": getattr(s, "alerts", []),
        }
        for s in sessions
    ]


@router.get("/api/sessions/{call_sid}/messages")
async def get_session_messages(call_sid: str):
    session = store.get(call_sid)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "messages": [
            {"role": t["role"], "content": t["content"], "timestamp": t["timestamp"]}
            for t in session.transcript
        ]
    }


@router.get("/api/sessions/{call_sid}/context")
async def get_session_context(call_sid: str):
    session = store.get(call_sid)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get CI events if available
    from twilio_observe.main import ci_middleware
    ci_events = ci_middleware.get_events(call_sid)

    return {
        "callSid": session.call_sid,
        "callerNumber": session.caller_number,
        "status": session.status,
        "csat": session.csat,
        "topic": session.topic,
        "coaching_instructions": session.coaching_instructions,
        "ci_events": ci_events,
        "alerts": getattr(session, "alerts", []),
    }
