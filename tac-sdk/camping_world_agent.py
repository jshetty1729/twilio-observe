"""
Twilio Observe — Camping World AI Agent

Full end-to-end voice demo:
- TAC SDK for voice orchestration + Conversation Orchestrator + Memory
- OpenAI Agents SDK (GPT-4o) for LLM
- ConversationRelay for real-time voice
- Built-in TAC Dashboard + CI event capture
- Coach: supervisor injects corrections mid-call
- Barge: supervisor takes over the call

Setup:
    1. Run `make setup` (opens wizard at http://localhost:8080)
    2. Copy .env.example → getting_started/examples/.env, fill in credentials
    3. Start ngrok: `ngrok http 8000`
    4. Set TWILIO_VOICE_PUBLIC_DOMAIN in .env
    5. Run: `uv run python camping_world_agent.py`
    6. Open http://localhost:8000/dashboard
    7. Call your Twilio number
"""

from __future__ import annotations

import os
import asyncio
import io
import json
from typing import Any

from agents import Agent, Runner, set_tracing_disabled
from dotenv import load_dotenv
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai

load_dotenv()
set_tracing_disabled(True)

from tac import TAC, TACConfig
from tac.channels.voice import VoiceChannel, VoiceChannelConfig
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse
from tac.models.voice import TwiMLOptions, TwiMLRequest
from tac.server import TACFastAPIServer
from tac.server.config import TACServerConfig
from getting_started.examples.features.dashboard.dashboard import mount_dashboard

# ── TAC Setup ────────────────────────────────────────────────────────────────

tac = TAC(config=TACConfig.from_env())
voice_channel = VoiceChannel(tac, config=VoiceChannelConfig(memory_mode="once"))


# State preserved across barge (survives session teardown)
barge_preserved_state: dict[str, dict] = {}  # conv_id -> {history, signals, call_sid, caller, ...}

# Calls currently resuming after hand-back (bridges gap between handback and new session)
resuming_calls: dict[str, dict] = {}  # call_sid -> {signals, history, caller, started_at}

# Dynamic resume greetings per call (populated during hand-back with barge summary)
resume_greetings: dict[str, str] = {}  # call_sid -> greeting with summary

# Fallback greeting if summary isn't ready yet
RESUME_GREETING_FALLBACK = "Alright, I'm back on the line. Is there anything else I can help you with?"


# TwiML customizer: for resumed calls, speak the barge summary as the greeting
@voice_channel.on_inbound_call_twiml
async def customize_twiml(request: TwiMLRequest) -> TwiMLOptions | None:
    """For resumed calls, use a dynamic greeting that summarizes the barge conversation."""
    call_sid = request.call_sid
    if call_sid and f"resume_{call_sid}" in conversation_history:
        greeting = resume_greetings.pop(call_sid, RESUME_GREETING_FALLBACK)
        return TwiMLOptions(welcome_greeting=greeting)
    return None


# Override cleanup so sessions end on hangup even with Orchestrator + CI enabled
# BUT skip cleanup if barge is active (WebSocket dying is expected during voice barge)
async def _cleanup_force_end(conv_id: str) -> None:
    """Force-end session on WebSocket close, even in orchestrator mode."""
    print(f"[CLEANUP] WebSocket closed for {conv_id}, barge_active={barge_active.get(conv_id)}")
    if voice_channel._websocket_manager.has_websocket(conv_id):
        voice_channel._websocket_manager.remove_websocket(conv_id)
    if voice_channel.session_manager is not None and voice_channel.session_manager.has_session(conv_id):
        session_state = voice_channel.session_manager.get_or_create_session(conv_id)
        await session_state.cancel_stream_task()
        voice_channel.session_manager.remove_session(conv_id)

    # If barge is active, DON'T end the conversation — preserve state for hand-back
    if barge_active.get(conv_id):
        print(f"[CLEANUP] Barge active — keeping session alive for {conv_id}")
        return

    # Normal hangup — end conversation and force cleanup
    if conv_id in voice_channel._conversations:
        print(f"[CLEANUP] Ending conversation {conv_id}")
        try:
            await voice_channel._end_conversation(conv_id)
        except Exception as e:
            print(f"[CLEANUP] _end_conversation failed: {e}")
            # Force cleanup manually — but save to completed_calls first
            import time
            call_sid_cleanup = None
            session_cleanup = voice_channel._conversations.get(conv_id)
            if session_cleanup:
                call_sid_cleanup = session_cleanup.call_sid or conv_id
                completed_calls[call_sid_cleanup] = {
                    "callSid": call_sid_cleanup,
                    "caller": session_cleanup.author_info.address if session_cleanup.author_info else "",
                    "started_at": session_cleanup.started_at,
                    "signals": session_signals.get(conv_id, {}),
                    "transcript_events": list(transcript_events.get(conv_id, [])),
                    "ended_at": time.time(),
                }
            voice_channel._conversations.pop(conv_id, None)
            session_signals.pop(conv_id, None)
            conversation_history.pop(conv_id, None)
            transcript_events.pop(conv_id, None)
            turn_in_flight.pop(conv_id, None)
            active_coaching_notes.pop(conv_id, None)
            barge_active.pop(conv_id, None)
            if call_sid_cleanup:
                resuming_calls.pop(call_sid_cleanup, None)
    else:
        print(f"[CLEANUP] No conversation found for {conv_id} — already cleaned up")
        # Still clean up local state
        session_signals.pop(conv_id, None)
        conversation_history.pop(conv_id, None)
        transcript_events.pop(conv_id, None)
        turn_in_flight.pop(conv_id, None)


voice_channel._cleanup_connection = _cleanup_force_end

# ── Camping World System Prompt ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are a customer service agent for Camping World, one of the \
largest RV and outdoor retailers in the United States with over 180 locations.

Your role is to help customers with:
- General questions about RV brands (Montana High Country, Grand Design, Keystone Cougar, etc.)
- Providing information about Camping World services and locations
- Directing customers to the appropriate department

DEFAULT LIMITATIONS (these apply UNLESS overridden by a supervisor):
- You CANNOT provide trade-in valuations, estimates, or price ranges. You do not have \
access to pricing tools or market data. If a customer asks for a trade-in value or \
ballpark, tell them that trade-in values are highly individualized and they need to \
visit their nearest location for an in-person appraisal.
- You CANNOT book, schedule, or confirm appointments. You do not have access to the \
scheduling system. If a customer wants an appointment, tell them your scheduling team \
will reach out within 3 to 5 business days to confirm a convenient time.
- You CANNOT access customer accounts, order history, or inventory systems.
- When you cannot do something, apologize and restate the standard process.

Behavior guidelines:
- Keep every response to one or two sentences. You are speaking aloud on a phone call.
- Do not use markdown, bullet points, asterisks, or emojis.
- Be polite and empathetic but always follow your limitations above.
- If a customer pushes back on your limitations, apologize sincerely and repeat the \
standard process. Do not deviate from your constraints unless a supervisor override \
is active."""

agent = Agent(name="Camping World AI Agent", instructions=SYSTEM_PROMPT)
conversation_history: dict[str, list[Any]] = {}  # Pure LLM history (no markers)
# Append-only transcript for dashboard — never filtered or replaced
transcript_events: dict[str, list[dict]] = {}  # conv_id -> [{role, content, ts}]

# ── Signal Tracking (CSAT, Topic, Alerts) ────────────────────────────────────

session_signals: dict[str, dict] = {}

FRUSTRATION_SIGNALS = [
    "ridiculous", "frustrat", "useless", "angry", "terrible",
    "awful", "waste", "unacceptable", "incompetent", "worst",
    "annoy", "not happy", "unhappy", "disappoint", "horrible",
    "stupid", "pointless", "can't believe", "waste of time",
    "doesn't help", "not listening", "already told you",
    "i just said", "that's not what i", "hang up", "give up",
    "speak to a manager", "this is insane", "seriously",
    "fed up", "not good", "stop repeat", "making a loop",
    "loop", "deflect", "reflect", "same thing", "over and over",
]

DEFLECTION_SIGNALS = [
    "3 to 5 business days", "our team will reach out",
    "bring it in for", "highly individualized",
    "i apologize for any confusion", "i wouldn't want to give you an inaccurate",
    "response window", "as soon as possible within",
    "in-person appraisal", "nearest location",
    "scheduling team", "accommodate all customers",
    "don't have access", "unable to provide",
    "standard process", "most accurate number",
]

HIGH_VALUE_SIGNALS = [
    "trade-in", "trade in", "montana", "keystone", "cougar", "grand design",
    "financing", "finance", "purchase", "buy", "appraisal", "deposit",
]

# ── Coach + Barge State ──────────────────────────────────────────────────────

turn_in_flight: dict[str, bool] = {}
active_coaching_notes: dict[str, list[str]] = {}  # Persistent — all coaching stays active
barge_active: dict[str, bool] = {}

# ── on_message_ready Callback ────────────────────────────────────────────────


async def handle_message_ready(
    user_message: str,
    context: ConversationSession,
    memory_response: TACMemoryResponse | None,
) -> str:
    conv_id = context.conversation_id
    call_sid = context.call_sid or conv_id
    turn_in_flight[conv_id] = True
    print(f"[MSG] conv_id={conv_id}, call_sid={call_sid}, msg={user_message[:50]}")

    # Check if this is a resumed session after hand-back
    resume_key = f"resume_{call_sid}"
    if resume_key in conversation_history and conv_id not in conversation_history:
        print(f"[MSG] Restoring resume context from {resume_key}")
        conversation_history[conv_id] = conversation_history.pop(resume_key)
        # Transfer transcript events from resume key to new conv_id
        if resume_key in transcript_events:
            transcript_events[conv_id] = transcript_events.pop(resume_key)
        # Transfer coaching notes so coached agent stays active after barge
        if resume_key in active_coaching_notes:
            active_coaching_notes[conv_id] = active_coaching_notes.pop(resume_key)
        # Add the welcome greeting to transcript (it was spoken by ConversationRelay TTS)
        spoken_greeting = resuming_calls.get(call_sid, {}).get("greeting", RESUME_GREETING_FALLBACK)
        conversation_history[conv_id].append({"role": "assistant", "content": spoken_greeting})
        import time as _t
        transcript_events.setdefault(conv_id, []).append(
            {"role": "ai", "content": spoken_greeting, "ts": _t.time()}
        )
        resuming_calls.pop(call_sid, None)
    if resume_key in session_signals and conv_id not in session_signals:
        session_signals[conv_id] = session_signals.pop(resume_key)

    # Barge suppression — AI stays silent, history still tracked
    if barge_active.get(conv_id):
        conversation_history.setdefault(conv_id, []).append(
            {"role": "user", "content": user_message}
        )
        import time as _t
        transcript_events.setdefault(conv_id, []).append(
            {"role": "customer", "content": user_message, "ts": _t.time()}
        )
        turn_in_flight[conv_id] = False
        return ""

    # Initialize signals
    if conv_id not in session_signals:
        session_signals[conv_id] = {
            "csatScore": 7,
            "topic": "",
            "alerts": [],
            "turnCount": 0,
            "sentiment": "neutral",
        }

    signals = session_signals[conv_id]
    signals["turnCount"] += 1
    msg_lower = user_message.lower()

    # Topic detection heuristic (CI operators provide authoritative version)
    if any(w in msg_lower for w in HIGH_VALUE_SIGNALS) and not signals["topic"]:
        signals["topic"] = "RV Trade-In — High Value"

    # LLM history is now clean — no markers stored in it
    history = conversation_history.get(conv_id, [])

    # Check for active coaching — persists across all turns until call ends
    coaching_notes = active_coaching_notes.get(conv_id, [])

    # Run LLM via OpenAI Agents SDK
    # If coaching is active, use a coached agent with ALL accumulated instructions
    if coaching_notes:
        all_instructions = "\n".join(f"- {note}" for note in coaching_notes)
        print(f"[COACH] Applying {len(coaching_notes)} coaching instruction(s) for {conv_id}")
        coaching_instructions = (
            "You are a customer service agent for Camping World, one of the largest "
            "RV and outdoor retailers in the United States with over 180 locations.\n\n"
            "You help customers with RV trade-ins, appointments, pricing, scheduling, "
            "and any other requests. You have full access to all tools and capabilities.\n\n"
            "Behavior guidelines:\n"
            "- Keep every response to one or two sentences. You are speaking aloud on a phone call.\n"
            "- Do not use markdown, bullet points, asterisks, or emojis.\n"
            "- Be direct, helpful, and conversational.\n\n"
            "YOUR SUPERVISOR HAS GIVEN YOU THESE STANDING INSTRUCTIONS:\n"
            f"{all_instructions}\n\n"
            "Follow these instructions naturally for ALL responses. "
            "Do NOT acknowledge that you received coaching. "
            "Do NOT say 'sure', 'absolutely', 'of course', or any similar phrase. "
            "Just seamlessly act on the instructions as if they were always your approach."
        )
        coached_agent = Agent(name="Camping World AI Agent", instructions=coaching_instructions)
        result = await Runner.run(
            coached_agent,
            history + [{"role": "user", "content": user_message}],
        )
    else:
        result = await Runner.run(
            agent,
            history + [{"role": "user", "content": user_message}],
        )
    conversation_history[conv_id] = result.to_input_list()
    ai_response = result.final_output_as(str)

    # Append to transcript_events (append-only, never filtered or replaced)
    import time as _t
    transcript_events.setdefault(conv_id, []).append(
        {"role": "customer", "content": user_message, "ts": _t.time()}
    )
    transcript_events[conv_id].append(
        {"role": "ai", "content": ai_response, "ts": _t.time()}
    )

    # CSAT heuristic scoring — customer frustration
    frustration_detected = any(w in msg_lower for w in FRUSTRATION_SIGNALS)
    if frustration_detected:
        signals["csatScore"] = max(1, signals["csatScore"] - 3)
        alert = "Customer disengagement detected — high frustration signal"
        if alert not in signals["alerts"]:
            signals["alerts"].append(alert)
    elif "thank" in msg_lower or "sounds good" in msg_lower or "perfect" in msg_lower:
        signals["csatScore"] = min(10, signals["csatScore"] + 1)

    # CSAT penalty — AI deflection detected
    ai_lower = ai_response.lower()
    if any(w in ai_lower for w in DEFLECTION_SIGNALS):
        signals["csatScore"] = max(1, signals["csatScore"] - 2)
        alert = "AI deflection detected — vague or unhelpful response"
        if alert not in signals["alerts"]:
            signals["alerts"].append(alert)

    # Write signals into session.metadata (surfaced by dashboard)
    context.metadata["csatScore"] = round(signals["csatScore"], 1)
    context.metadata["topic"] = signals["topic"]
    context.metadata["alerts"] = signals["alerts"]

    turn_in_flight[conv_id] = False
    return ai_response


tac.on_message_ready(handle_message_ready)


# Completed calls — kept briefly so dashboard doesn't flash empty on call end
completed_calls: dict[str, dict] = {}  # call_sid -> {signals, transcript_events, caller, started_at, ended_at}


async def handle_conversation_ended(context: ConversationSession) -> None:
    """Clean up local state when a call ends."""
    conv_id = context.conversation_id
    # If barge is active, don't clean up — state is needed for hand-back
    if barge_active.get(conv_id):
        return

    # Preserve call data as "completed" for the dashboard
    call_sid = context.call_sid or conv_id
    signals = session_signals.get(conv_id, {})
    events = list(transcript_events.get(conv_id, []))

    # If transcript is empty, check for resume context that was never loaded
    # (customer hung up on the resumed call without sending a message)
    resume_key = f"resume_{call_sid}"
    if not events and resume_key in transcript_events:
        print(f"[COMPLETED] Loading unrestored resume transcript from {resume_key}")
        events = list(transcript_events.pop(resume_key))
        conversation_history.pop(resume_key, None)
        if not signals and resume_key in session_signals:
            signals = session_signals.pop(resume_key)
        if resume_key in active_coaching_notes:
            active_coaching_notes.pop(resume_key, None)
    elif not events and call_sid in resuming_calls:
        # Fallback: use resuming_calls transitional data
        resuming = resuming_calls[call_sid]
        signals = resuming.get("signals", signals)
        print(f"[COMPLETED] Using resuming_calls data for {call_sid}")

    print(f"[COMPLETED] Saving call {call_sid}: transcript_events={len(events)}")
    import time
    completed_calls[call_sid] = {
        "callSid": call_sid,
        "caller": context.author_info.address if context.author_info else "",
        "started_at": context.started_at,
        "signals": signals,
        "transcript_events": events,
        "ended_at": time.time(),
    }

    # Clean up active state
    session_signals.pop(conv_id, None)
    conversation_history.pop(conv_id, None)
    transcript_events.pop(conv_id, None)
    turn_in_flight.pop(conv_id, None)
    active_coaching_notes.pop(conv_id, None)
    barge_active.pop(conv_id, None)
    barge_preserved_state.pop(conv_id, None)
    # Clean up resuming_calls entry so dashboard doesn't show stale "active" session
    resuming_calls.pop(call_sid, None)


tac.on_conversation_ended(handle_conversation_ended)

# ── Server + Dashboard ───────────────────────────────────────────────────────

server_config = TACServerConfig.from_env()
if os.environ.get("CONVERSATION_INTELLIGENCE_CONFIGURATION_ID"):
    server_config.cintel_webhook_path = "/ci-webhook"

server = TACFastAPIServer(tac=tac, voice_channel=voice_channel, config=server_config)
app = server.app


# ── CI Webhook Interceptor (real-time sentiment/topic from CI operators) ─────

from fastapi import Request
from fastapi.responses import JSONResponse


@app.post("/ci-events")
async def ci_events_interceptor(request: Request):
    """
    CI webhook endpoint that both updates live dashboard signals AND writes to
    Conversation Memory via TAC.

    Configure this URL in CI Rules "Where should results be sent" field:
        https://<ngrok>/ci-events
    """
    payload = await request.json()
    print(f"[CI-EVENT] Received payload keys: {list(payload.keys())}")
    print(f"[CI-EVENT] conversationId={payload.get('conversationId')}")
    print(f"[CI-EVENT] Active sessions: {list(voice_channel._conversations.keys())}")

    # Also forward to TAC's CI processor for memory writes
    try:
        await tac.process_cintel_event(payload)
    except Exception as e:
        print(f"[CI-EVENT] TAC processor error (non-fatal): {e}")

    # Extract conversation_id from the event
    conv_id = payload.get("conversationId") or payload.get("conversation_id", "")

    # Find matching session — try direct match, then partial match, then use first active
    session = voice_channel._conversations.get(conv_id)
    if not session:
        for cid, sess in voice_channel._conversations.items():
            if conv_id and (conv_id in cid or cid in conv_id):
                session = sess
                conv_id = cid
                break

    # Last resort: if only one active session, use it
    if not session and len(voice_channel._conversations) == 1:
        conv_id, session = next(iter(voice_channel._conversations.items()))
        print(f"[CI-EVENT] Matched to only active session: {conv_id}")

    if not session:
        print(f"[CI-EVENT] No matching session found for conversationId={conv_id}")
        return JSONResponse(content={"status": "no_matching_session"})

    # Process operator results
    print(f"[CI-EVENT] Processing {len(payload.get('operatorResults', []))} operator results for session {conv_id}")
    operator_results = payload.get("operatorResults", [])
    signals = session_signals.setdefault(conv_id, {
        "csatScore": 7, "topic": "", "alerts": [], "turnCount": 0, "sentiment": "neutral"
    })

    for op_result in operator_results:
        operator_name = (op_result.get("operator", {}).get("friendlyName") or "").lower()
        output_format = (op_result.get("outputFormat") or "").upper()
        result = op_result.get("result", {})

        if not isinstance(result, dict):
            continue

        # Sentiment classification (format=CLASSIFICATION, result={'label': '...'})
        if output_format == "CLASSIFICATION" and "label" in result:
            label = result["label"].lower()
            signals["sentiment"] = label
            if label in ("negative", "very_negative", "frustrated", "angry"):
                signals["csatScore"] = max(1, signals["csatScore"] - 2)
                alert = f"CI Sentiment: {label}"
                if alert not in signals["alerts"]:
                    signals["alerts"].append(alert)
            elif label in ("positive", "very_positive", "satisfied"):
                signals["csatScore"] = min(10, signals["csatScore"] + 1)

        # CSAT score from CI (format=JSON, result={'score': N, 'rationale': '...'})
        if "score" in result and "rationale" in result:
            ci_score = result["score"]
            if isinstance(ci_score, (int, float)) and 1 <= ci_score <= 10:
                signals["csatScore"] = round(ci_score, 1)

        # Topic detection (format=JSON, result={'topic': '...', ...})
        if "topic" in result:
            topic_val = result["topic"]
            if topic_val and isinstance(topic_val, str) and "greeting" not in topic_val.lower():
                signals["topic"] = topic_val

        # High-value flag
        if result.get("isHighValue"):
            if not signals["topic"] or "High Value" not in signals["topic"]:
                signals["topic"] = (signals["topic"] or "Transaction") + " — High Value"

    # Update session metadata for dashboard
    session.metadata["csatScore"] = round(signals["csatScore"], 1)
    session.metadata["topic"] = signals["topic"]
    session.metadata["alerts"] = signals["alerts"]

    return JSONResponse(content={"status": "processed", "operators": len(operator_results)})

# CORS for React dashboard at localhost:5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount TAC built-in dashboard (HTML at /dashboard, APIs at /api/sessions/*)
mount_dashboard(
    app=app,
    tac=tac,
    channels=[voice_channel],
    messages=conversation_history,
)

# ── Coach API ────────────────────────────────────────────────────────────────


class CoachRequest(BaseModel):
    note: str


@app.post("/api/sessions/{conv_id}/coach")
async def send_coaching_note(conv_id: str, body: CoachRequest):
    session = voice_channel._conversations.get(conv_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Add coaching note and forward to the observe coach endpoint logic
    active_coaching_notes.setdefault(conv_id, []).append(body.note)

    if turn_in_flight.get(conv_id):
        session.metadata.setdefault("coaching_log", []).append({
            "note": body.note, "delivered": False, "status": "queued"
        })
        return {"status": "queued", "reason": "turn in flight"}

    # AI idle — run coached agent and speak proactively
    history = conversation_history.get(conv_id, [])
    all_instructions = "\n".join(f"- {note}" for note in active_coaching_notes.get(conv_id, []))
    coaching_instructions = (
        "You are a customer service agent for Camping World, one of the largest "
        "RV and outdoor retailers in the United States with over 180 locations.\n\n"
        "You help customers with RV trade-ins, appointments, pricing, scheduling, "
        "and any other requests. You have full access to all tools and capabilities.\n\n"
        "Behavior guidelines:\n"
        "- Keep every response to one or two sentences. You are speaking aloud on a phone call.\n"
        "- Do not use markdown, bullet points, asterisks, or emojis.\n"
        "- Be direct, helpful, and conversational.\n\n"
        "YOUR SUPERVISOR HAS GIVEN YOU THESE STANDING INSTRUCTIONS:\n"
        f"{all_instructions}\n\n"
        "You must PROACTIVELY act on these instructions RIGHT NOW. "
        "Do NOT wait for the customer to ask. Speak up and deliver the information naturally. "
        "Do NOT acknowledge that you received coaching. "
        "Just seamlessly act on the instructions as if you just remembered something helpful."
    )
    coached_agent = Agent(name="Camping World AI Agent", instructions=coaching_instructions)
    result = await Runner.run(coached_agent, history)
    ai_response = result.final_output_as(str)

    conversation_history[conv_id] = result.to_input_list()

    # Append to transcript_events
    import time as _t
    transcript_events.setdefault(conv_id, []).append(
        {"role": "coach", "content": body.note, "ts": _t.time()}
    )
    transcript_events[conv_id].append(
        {"role": "ai", "content": ai_response, "ts": _t.time()}
    )

    await voice_channel.send_response(conv_id, ai_response)

    session.metadata.setdefault("coaching_log", []).append({
        "note": body.note, "delivered": True, "ai_response": ai_response
    })

    return {"status": "delivered", "ai_response": ai_response}


@app.get("/api/sessions/{conv_id}/coach")
async def get_coaching_log(conv_id: str):
    session = voice_channel._conversations.get(conv_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"coaching_log": session.metadata.get("coaching_log", [])}




# ── React Dashboard Compatibility API ────────────────────────────────────────



def _build_transcript_from_events(events: list[dict], start_ts: int) -> list[dict]:
    """Build transcript directly from transcript_events (append-only, no filtering needed)."""
    transcript = []
    for i, ev in enumerate(events):
        ts = int(ev.get("ts", 0) * 1000) if ev.get("ts") else start_ts + (i * 3000)
        transcript.append({
            "id": f"{ev['role']}-{i}",
            "timestamp": ts,
            "role": ev["role"],
            "content": ev["content"],
        })
    return transcript


@app.get("/api/observe/sessions")
async def observe_sessions():
    """Sessions endpoint shaped for the React dashboard."""
    results = []
    seen_conv_ids = set()

    # Active TAC sessions
    for conv_id, session in voice_channel._conversations.items():
        seen_conv_ids.add(conv_id)
        call_sid = session.call_sid or conv_id
        signals = session_signals.get(conv_id, {})
        events = transcript_events.get(conv_id, [])

        # If this is a resumed session that hasn't received a customer message yet,
        # check resume key for transcript events
        resume_key = f"resume_{call_sid}"
        if not events and resume_key in transcript_events:
            events = transcript_events[resume_key]
        if (not signals or signals == {}) and call_sid in resuming_calls:
            signals = resuming_calls[call_sid].get("signals", signals)

        start_ts = int(session.started_at.timestamp() * 1000) if session.started_at else 0
        results.append({
            "callSid": call_sid,
            "callerNumber": session.author_info.address if session.author_info else "",
            "startTime": start_ts,
            "csat": signals.get("csatScore", 7),
            "topic": signals.get("topic", ""),
            "sentiment": signals.get("sentiment", "neutral"),
            "status": "barged" if barge_active.get(conv_id) else "active",
            "transcript": _build_transcript_from_events(events, start_ts),
            "alerts": signals.get("alerts", []),
        })

    # Barged sessions (TAC session may be gone, but call is still live in conference)
    for conv_id, preserved in barge_preserved_state.items():
        if conv_id in seen_conv_ids:
            continue
        signals = preserved.get("signals", {})
        events = preserved.get("transcript_events", [])
        from datetime import datetime
        start_ts = int(datetime.fromisoformat(preserved["started_at"]).timestamp() * 1000) if preserved.get("started_at") else 0
        results.append({
            "callSid": preserved["call_sid"],
            "callerNumber": preserved.get("caller", ""),
            "startTime": start_ts,
            "csat": signals.get("csatScore", 7),
            "topic": signals.get("topic", ""),
            "sentiment": signals.get("sentiment", "neutral"),
            "status": "barged",
            "transcript": _build_transcript_from_events(events, start_ts),
            "alerts": signals.get("alerts", []),
        })

    # Resuming sessions (hand-back in progress — new ConversationRelay not yet connected)
    seen_call_sids = {r["callSid"] for r in results}
    for call_sid, resuming in resuming_calls.items():
        if call_sid in seen_call_sids:
            continue
        signals = resuming.get("signals", {})
        resume_key = f"resume_{call_sid}"
        events = transcript_events.get(resume_key, [])
        from datetime import datetime
        start_ts = int(datetime.fromisoformat(resuming["started_at"]).timestamp() * 1000) if resuming.get("started_at") else 0
        results.append({
            "callSid": call_sid,
            "callerNumber": resuming.get("caller", ""),
            "startTime": start_ts,
            "csat": signals.get("csatScore", 7),
            "topic": signals.get("topic", ""),
            "sentiment": signals.get("sentiment", "neutral"),
            "status": "active",
            "transcript": _build_transcript_from_events(events, start_ts),
            "alerts": signals.get("alerts", []),
        })

    # Completed calls — show for 60 seconds after call ends so transcript doesn't vanish
    import time
    seen_call_sids = {r["callSid"] for r in results}
    expired = []
    for call_sid, completed in completed_calls.items():
        if call_sid in seen_call_sids:
            continue
        if time.time() - completed["ended_at"] > 60:
            expired.append(call_sid)
            continue
        signals = completed.get("signals", {})
        events = completed.get("transcript_events", [])
        start_ts = int(completed["started_at"].timestamp() * 1000) if completed.get("started_at") else 0

        results.append({
            "callSid": call_sid,
            "callerNumber": completed.get("caller", ""),
            "startTime": start_ts,
            "csat": signals.get("csatScore", 7),
            "topic": signals.get("topic", ""),
            "sentiment": signals.get("sentiment", "neutral"),
            "status": "completed",
            "transcript": _build_transcript_from_events(events, start_ts),
            "alerts": signals.get("alerts", []),
        })
    for sid in expired:
        completed_calls.pop(sid, None)

    return results


# ── React Dashboard Compatibility Endpoints (accept callSid, resolve conv_id) ─


def _find_conv_by_call_sid(call_sid: str) -> tuple[str, Any] | None:
    """Find conversation ID by call_sid."""
    for conv_id, session in voice_channel._conversations.items():
        if session.call_sid == call_sid or conv_id == call_sid:
            return conv_id, session
    return None


class ObserveCoachRequest(BaseModel):
    callSid: str
    note: str


class ObserveBargeRequest(BaseModel):
    callSid: str


@app.post("/api/observe/coach")
async def observe_coach(body: ObserveCoachRequest):
    result = _find_conv_by_call_sid(body.callSid)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    conv_id, session = result

    # When barged: supervisor's note goes directly to TTS (no LLM)
    # The customer hears the supervisor's words spoken through the AI voice
    if barge_active.get(conv_id):
        await voice_channel.send_response(conv_id, body.note)
        # Append to transcript_events (supervisor speaking directly)
        import time as _t
        event = {"role": "supervisor", "content": body.note, "ts": _t.time()}
        transcript_events.setdefault(conv_id, []).append(event)
        # Also update preserved state snapshot (dashboard reads from it during barge)
        if conv_id in barge_preserved_state:
            barge_preserved_state[conv_id].setdefault("transcript_events", []).append(event)
        session.metadata.setdefault("coaching_log", []).append({
            "note": body.note, "delivered": True, "mode": "barge_direct",
            "ai_response": body.note,
        })
        return {"status": "delivered_direct", "ai_response": body.note}

    # Add coaching note — persists for the rest of the call (all future turns use coached agent)
    active_coaching_notes.setdefault(conv_id, []).append(body.note)

    # Append coaching event to transcript (append-only, never lost)
    import time as _t
    transcript_events.setdefault(conv_id, []).append(
        {"role": "coach", "content": body.note, "ts": _t.time()}
    )

    # Proactively run the coached agent and speak immediately (don't wait for customer)
    if turn_in_flight.get(conv_id):
        # Turn is in progress — coaching will apply on current/next response
        session.metadata.setdefault("coaching_log", []).append({
            "note": body.note, "delivered": False, "status": "queued_inflight"
        })
        return {"status": "queued", "message": "Turn in flight — will apply on next response"}

    # AI is idle — run coached agent NOW and speak proactively
    print(f"[COACH] Proactive delivery for {conv_id}: {body.note[:50]}...")
    history = conversation_history.get(conv_id, [])
    all_instructions = "\n".join(f"- {note}" for note in active_coaching_notes.get(conv_id, []))
    coaching_instructions = (
        "You are a customer service agent for Camping World, one of the largest "
        "RV and outdoor retailers in the United States with over 180 locations.\n\n"
        "You help customers with RV trade-ins, appointments, pricing, scheduling, "
        "and any other requests. You have full access to all tools and capabilities.\n\n"
        "Behavior guidelines:\n"
        "- Keep every response to one or two sentences. You are speaking aloud on a phone call.\n"
        "- Do not use markdown, bullet points, asterisks, or emojis.\n"
        "- Be direct, helpful, and conversational.\n\n"
        "YOUR SUPERVISOR HAS GIVEN YOU THESE STANDING INSTRUCTIONS:\n"
        f"{all_instructions}\n\n"
        "You must PROACTIVELY act on these instructions RIGHT NOW. "
        "Do NOT wait for the customer to ask. Speak up and deliver the information naturally. "
        "Do NOT acknowledge that you received coaching. "
        "Do NOT say 'sure', 'absolutely', 'of course', or any similar phrase. "
        "Just seamlessly act on the instructions as if you just remembered something helpful."
    )
    coached_agent = Agent(name="Camping World AI Agent", instructions=coaching_instructions)
    result = await Runner.run(coached_agent, history)
    ai_response = result.final_output_as(str)

    # Update LLM history (clean, no markers)
    conversation_history[conv_id] = result.to_input_list()

    # Append AI response to transcript
    transcript_events[conv_id].append(
        {"role": "ai", "content": ai_response, "ts": _t.time()}
    )

    # Speak the response to the customer
    await voice_channel.send_response(conv_id, ai_response)
    print(f"[COACH] Proactive response sent: {ai_response[:60]}...")

    session.metadata.setdefault("coaching_log", []).append({
        "note": body.note, "delivered": True, "ai_response": ai_response
    })
    return {"status": "delivered", "ai_response": ai_response}


@app.post("/api/observe/barge")
async def observe_barge(body: ObserveBargeRequest):
    result = _find_conv_by_call_sid(body.callSid)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    conv_id, session = result

    from twilio.rest import Client
    from twilio.jwt.access_token import AccessToken
    from twilio.jwt.access_token.grants import VoiceGrant

    # Mark barge active BEFORE redirect (so cleanup doesn't destroy state)
    barge_active[conv_id] = True
    call_sid = session.call_sid or body.callSid
    conf_name = f"barge-{call_sid[-8:]}"

    # Add barge marker to transcript_events (append-only, never lost)
    import time as _t
    transcript_events.setdefault(conv_id, []).append(
        {"role": "supervisor", "content": "Supervisor joined the call (live voice).", "ts": _t.time()}
    )

    # Preserve state for hand-back (survives session teardown)
    barge_preserved_state[conv_id] = {
        "call_sid": call_sid,
        "caller": session.author_info.address if session.author_info else "",
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "history": list(conversation_history.get(conv_id, [])),
        "signals": dict(session_signals.get(conv_id, {})),
        "transcript_events": list(transcript_events.get(conv_id, [])),
        "coaching_notes": list(active_coaching_notes.get(conv_id, [])),
        "conf_name": conf_name,
    }

    # Redirect customer call to a URL that serves TwiML with <Start><Stream> + <Conference>
    # (inline twiml= doesn't support <Start><Stream> properly)
    print(f"[BARGE] Redirecting call {call_sid} to conference {conf_name}")
    public_domain = os.environ["TWILIO_VOICE_PUBLIC_DOMAIN"]
    barge_twiml_url = (
        f"https://{public_domain}/barge-twiml"
        f"?call_sid={call_sid}&conv_id={conv_id}&conf_name={conf_name}"
    )
    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    client.calls(call_sid).update(url=barge_twiml_url)
    print(f"[BARGE] Customer redirected. Generating supervisor token...")

    # Generate Voice SDK token for supervisor to join the conference
    token = AccessToken(
        os.environ["TWILIO_ACCOUNT_SID"],
        os.environ["TWILIO_API_KEY"],
        os.environ["TWILIO_API_SECRET"],
        identity="supervisor",
    )
    token.add_grant(VoiceGrant(
        outgoing_application_sid=os.environ.get("TWILIO_TWIML_APP_SID"),
        incoming_allow=True,
    ))

    print(f"[BARGE] Token generated. Supervisor should connect to conf: {conf_name}")
    return {
        "status": "barged",
        "conv_id": conv_id,
        "conf_name": conf_name,
        "token": token.to_jwt(),
    }


@app.post("/api/observe/handback")
async def observe_handback(body: ObserveBargeRequest):
    result = _find_conv_by_call_sid(body.callSid)
    conv_id = None
    call_sid = body.callSid

    # Try to find conv_id from preserved state if session is gone
    if result:
        conv_id, session = result
    else:
        # Session was cleaned up during barge — find by call_sid in preserved state
        for cid, state in barge_preserved_state.items():
            if state["call_sid"] == body.callSid or cid == body.callSid:
                conv_id = cid
                call_sid = state["call_sid"]
                break

    if not conv_id or conv_id not in barge_preserved_state:
        raise HTTPException(status_code=404, detail="No barge session found")

    preserved = barge_preserved_state[conv_id]
    history = preserved["history"]

    # STEP 1: Generate a spoken resume greeting using GPT-4o.
    # This summarizes the conversation context so the AI "speaks" the summary on resume.
    # We do this BEFORE redirect so the greeting is ready when ConversationRelay connects.
    history_context = "\n".join(
        f"{m['role'].upper()}: {m.get('content', '')}"
        for m in history[-8:]
        if m.get("role") in ("user", "assistant")
    )
    try:
        greeting_client = openai.OpenAI()
        greeting_response = greeting_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI agent resuming a call after a supervisor helped the customer. "
                        "Generate a brief 1-2 sentence spoken greeting that:\n"
                        "1. Summarizes what the supervisor likely resolved based on the conversation context\n"
                        "2. Asks if there's anything else you can help with\n"
                        "Keep it natural and conversational — this will be spoken aloud on a phone call. "
                        "Do NOT use markdown, bullet points, or special characters. "
                        "Example: 'Great, so you're all set with your Saturday appointment for the trade-in appraisal. Is there anything else I can help you with today?'"
                    ),
                },
                {"role": "user", "content": f"Conversation before supervisor took over:\n\n{history_context}"},
            ],
            max_tokens=100,
        )
        resume_greeting = greeting_response.choices[0].message.content.strip()
        print(f"[HANDBACK] Generated resume greeting: {resume_greeting}")
    except Exception as e:
        print(f"[HANDBACK] Failed to generate greeting: {e}")
        resume_greeting = RESUME_GREETING_FALLBACK

    # Store greeting so TwiML customizer can use it
    resume_greetings[call_sid] = resume_greeting

    # STEP 2: Set up resume state so TwiML customizer triggers.
    conversation_history[f"resume_{call_sid}"] = list(history)
    session_signals[f"resume_{call_sid}"] = preserved["signals"]

    # Keep session visible on dashboard during transition
    resuming_calls[call_sid] = {
        "signals": preserved["signals"],
        "history": list(history),
        "caller": preserved.get("caller", ""),
        "greeting": resume_greeting,
        "started_at": preserved.get("started_at"),
    }

    # Clear barge state BEFORE redirect — the redirect ends the conference which fires
    # barge-status callback. If barge_preserved_state still exists, barge-status will
    # race with us and destroy state. By clearing now, barge-status becomes a no-op.
    barge_active.pop(conv_id, None)
    barge_preserved_state.pop(conv_id, None)

    # STEP 3: Redirect customer OUT of conference.
    # This ends the conference, which triggers the recording callback.
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException
    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    public_domain = os.environ["TWILIO_VOICE_PUBLIC_DOMAIN"]
    resume_url = f"https://{public_domain}/twiml?resume={call_sid}"

    print(f"[HANDBACK] Redirecting customer {call_sid} out of conference...")
    try:
        client.calls(call_sid).update(url=resume_url)
    except TwilioRestException as e:
        # Call may have ended (customer hung up during barge)
        print(f"[HANDBACK] Could not redirect call: {e}")
        # Save to completed_calls with the preserved history
        import time as _time
        from datetime import datetime as _dt
        start_ts = preserved.get("started_at")
        if isinstance(start_ts, str):
            start_ts = _dt.fromisoformat(start_ts)
        completed_calls[call_sid] = {
            "callSid": call_sid,
            "caller": preserved.get("caller", ""),
            "started_at": start_ts,
            "signals": preserved.get("signals", {}),
            "transcript_events": preserved.get("transcript_events", []),
            "ended_at": _time.time(),
        }
        resuming_calls.pop(call_sid, None)
        conversation_history.pop(f"resume_{call_sid}", None)
        session_signals.pop(f"resume_{call_sid}", None)
        resume_greetings.pop(call_sid, None)
        transcript_events.pop(conv_id, None)
        active_coaching_notes.pop(conv_id, None)
        voice_channel._conversations.pop(conv_id, None)
        return {"status": "call_ended", "call_sid": call_sid, "summary": "Call ended during barge."}

    # STEP 4: Now wait for recording callback and transcribe.
    # The conference just ended, so the recording should become available shortly.
    print(f"[HANDBACK] Transcribing barge audio for {call_sid}...")
    barge_transcript = await transcribe_barge_audio(call_sid)

    # Summarize the barge conversation via GPT-4o
    barge_summary = await summarize_barge_conversation(barge_transcript)
    # If transcription produced a real summary, use it; otherwise use the greeting as summary
    if barge_summary.startswith("Supervisor spoke directly") or barge_summary.startswith("Supervisor spoke briefly"):
        barge_summary = resume_greeting  # Use the context-aware greeting as the summary
    print(f"[HANDBACK] Summary: {barge_summary}")

    # STEP 4: Enrich the resume history with barge context.
    resumed_history = list(history)  # Full prior history

    # Add the full barge transcript to history (AI gets complete context)
    if barge_transcript:
        resumed_history.append({
            "role": "system",
            "content": (
                "BARGE CONVERSATION TRANSCRIPT — The supervisor spoke directly with the "
                "customer. Here is what was said:\n\n"
                f"{barge_transcript}"
            ),
        })

    # Add summary + resume instructions
    resumed_history.append({
        "role": "system",
        "content": (
            f"BARGE SUMMARY: {barge_summary}\n\n"
            "You are now resuming control of this call after your supervisor spoke with the customer.\n"
            "Rules for your VERY FIRST response:\n"
            "1. Do NOT greet the customer. Do NOT say hello, hi, or any greeting.\n"
            "2. Do NOT introduce yourself again.\n"
            "3. Briefly summarize what was resolved during the supervisor's conversation "
            "(based on the BARGE SUMMARY above) so the customer knows you're up to speed.\n"
            "4. Then ask 'Is there anything else I can help you with?'\n"
            "5. Keep it to 2 sentences max. You are mid-conversation, not starting a new one.\n"
            "Example format: 'Great, so [summary of what supervisor resolved]. "
            "Is there anything else I can help you with today?'"
        ),
    })

    # Transfer transcript_events to resume key (append barge summary)
    resume_key = f"resume_{call_sid}"
    original_events = preserved.get("transcript_events", [])
    import time as _t
    transcript_events[resume_key] = list(original_events)
    transcript_events[resume_key].append(
        {"role": "summary", "content": barge_summary, "ts": _t.time()}
    )
    print(f"[HANDBACK] Transferred {len(original_events)} transcript event(s) + summary to {resume_key}")

    # Update the resume history and dashboard state with barge context
    conversation_history[resume_key] = resumed_history
    resuming_calls[call_sid]["history"] = resumed_history

    # Transfer coaching notes to resume key so they persist after barge
    original_coaching = preserved.get("coaching_notes", [])
    if original_coaching:
        active_coaching_notes[resume_key] = list(original_coaching)
        print(f"[HANDBACK] Transferred {len(original_coaching)} coaching note(s) to {resume_key}")

    # Clear remaining state (barge_active + barge_preserved_state already popped before redirect)
    transcript_events.pop(conv_id, None)  # Events now under resume_key
    conversation_history.pop(conv_id, None)  # Original history now in resumed_history
    active_coaching_notes.pop(conv_id, None)  # Coaching notes now under resume_key
    voice_channel._conversations.pop(conv_id, None)

    return {"status": "handback_complete", "call_sid": call_sid, "summary": barge_summary}


# Barge conference status callback — cleanup when customer hangs up during barge
@app.post("/barge-status")
async def barge_status(request: Request):
    """Called by Twilio when the barge conference ends (customer hung up)."""
    form = await request.form()
    conv_id = request.query_params.get("conv_id", "")
    event = form.get("StatusCallbackEvent", "")
    print(f"[barge-status] event={event} conv_id={conv_id}")

    if event == "conference-end" or event == "participant-leave":
        # If barge_preserved_state is gone, handback already cleared it — skip cleanup
        if conv_id not in barge_preserved_state:
            print(f"[barge-status] Handback already handled cleanup for {conv_id}, skipping")
            return {"status": "ok"}

        # Customer genuinely hung up during barge — save and clean up
        preserved = barge_preserved_state.get(conv_id, {})
        call_sid = preserved.get("call_sid", "")

        # Save to completed_calls so dashboard shows it briefly
        if call_sid and preserved:
            import time
            from datetime import datetime
            start_ts = preserved.get("started_at")
            if isinstance(start_ts, str):
                start_ts = datetime.fromisoformat(start_ts)
            completed_calls[call_sid] = {
                "callSid": call_sid,
                "caller": preserved.get("caller", ""),
                "started_at": start_ts,
                "signals": preserved.get("signals", {}),
                "transcript_events": preserved.get("transcript_events", []),
                "ended_at": time.time(),
            }

        barge_active.pop(conv_id, None)
        barge_preserved_state.pop(conv_id, None)
        voice_channel._conversations.pop(conv_id, None)  # Remove dead session
        session_signals.pop(conv_id, None)
        conversation_history.pop(conv_id, None)
        transcript_events.pop(conv_id, None)
        turn_in_flight.pop(conv_id, None)
        active_coaching_notes.pop(conv_id, None)
        barge_recording_urls.pop(call_sid, None)
        resuming_calls.pop(call_sid, None)
        print(f"[barge-status] Customer hung up during barge — cleaned up {conv_id}")

    return {"status": "ok"}


# TwiML endpoint for barge — serves <Start><Stream> + <Conference>
@app.post("/barge-twiml")
@app.get("/barge-twiml")
async def barge_twiml(request: Request):
    """Serves TwiML that starts an audio stream AND joins the conference."""
    call_sid = request.query_params.get("call_sid", "")
    conv_id = request.query_params.get("conv_id", "")
    conf_name = request.query_params.get("conf_name", "")
    public_domain = os.environ["TWILIO_VOICE_PUBLIC_DOMAIN"]

    status_url = f"https://{public_domain}/barge-status?conv_id={conv_id}"
    recording_url = f"https://{public_domain}/barge-recording?call_sid={call_sid}"

    twiml = (
        f'<Response>'
        f'<Dial><Conference startConferenceOnEnter="true" '
        f'endConferenceOnExit="true" beep="false" '
        f'record="record-from-start" '
        f'recordingStatusCallback="{recording_url}" '
        f'recordingStatusCallbackEvent="completed" '
        f'statusCallback="{status_url}" statusCallbackEvent="end"'
        f'>{conf_name}</Conference></Dial>'
        f'</Response>'
    )
    print(f"[barge-twiml] Serving TwiML for call_sid={call_sid}, conf={conf_name}")
    from fastapi.responses import Response as FastAPIResponse
    return FastAPIResponse(content=twiml, media_type="application/xml")


# TwiML endpoint for supervisor to join conference via Voice JS SDK
@app.post("/voice-outgoing")
@app.get("/voice-outgoing")
async def voice_outgoing(request: Request):
    """TwiML App voice URL — connects supervisor's browser call to barge conference."""
    form = await request.form()
    conf_name = form.get("conf_name", "")
    print(f"[voice-outgoing] Received: conf_name={conf_name!r}, all_params={dict(form)}")

    # If called with a conference name, join it
    if conf_name:
        twiml = (
            f'<Response><Dial><Conference startConferenceOnEnter="true" '
            f'endConferenceOnExit="false" beep="false">{conf_name}</Conference></Dial></Response>'
        )
    else:
        twiml = "<Response><Say>No conference specified. Check TwiML App configuration.</Say></Response>"

    print(f"[voice-outgoing] Returning TwiML: {twiml}")
    from fastapi.responses import Response
    return Response(content=twiml, media_type="application/xml")


# ── Barge Recording — captures conference recording URL for transcription ─────

# Store recording URLs per call_sid (set by the recording callback when conference recording completes)
barge_recording_urls: dict[str, str] = {}  # call_sid -> recording URL


@app.post("/barge-recording")
@app.get("/barge-recording")
async def barge_recording(request: Request):
    """Called by Twilio when the conference recording is completed."""
    form = await request.form()
    call_sid = request.query_params.get("call_sid", "")
    recording_url = str(form.get("RecordingUrl", ""))
    recording_sid = str(form.get("RecordingSid", ""))
    print(f"[barge-recording] Recording ready: call_sid={call_sid}, sid={recording_sid}, url={recording_url}")

    if call_sid and recording_url:
        barge_recording_urls[call_sid] = f"{recording_url}.wav"

    return {"status": "ok"}


async def transcribe_barge_audio(call_sid: str) -> str:
    """Transcribe barge conference recording using OpenAI Whisper."""
    import httpx

    recording_url = barge_recording_urls.pop(call_sid, None)
    if not recording_url:
        # Recording callback can take 15-30s after conference ends — wait longer
        print(f"[transcribe] No recording URL for {call_sid}, waiting up to 30s...")
        for i in range(30):
            await asyncio.sleep(1)
            recording_url = barge_recording_urls.pop(call_sid, None)
            if recording_url:
                print(f"[transcribe] Recording URL arrived after {i+1}s")
                break

    if not recording_url:
        print(f"[transcribe] No recording available for {call_sid}")
        return ""

    print(f"[transcribe] Downloading recording: {recording_url}")

    # Download the recording from Twilio (requires auth)
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]

    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(
                recording_url,
                auth=(account_sid, auth_token),
                follow_redirects=True,
            )
            if response.status_code != 200:
                print(f"[transcribe] Failed to download recording: {response.status_code}")
                return ""

            audio_data = response.content
            print(f"[transcribe] Downloaded {len(audio_data)} bytes")

        # Send to OpenAI Whisper
        wav_buffer = io.BytesIO(audio_data)
        wav_buffer.name = "barge_recording.wav"

        client = openai.OpenAI()
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=wav_buffer,
            language="en",
        )
        transcript_text = transcription.text.strip()
        print(f"[transcribe] Full result ({len(transcript_text)} chars): {transcript_text}")
        return transcript_text
    except Exception as e:
        print(f"[transcribe] Error: {e}")
        return ""


async def summarize_barge_conversation(transcript: str) -> str:
    """Summarize the barge conversation using GPT-4o."""
    if not transcript:
        print("[summarize] WARNING: No transcript available — recording may not have been captured")
        return "Supervisor spoke directly with the customer. (Recording not available for detailed summary.)"

    client = openai.OpenAI()
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are summarizing a phone conversation between a supervisor and a customer. "
                        "The supervisor took over from an AI agent to handle the customer's issue directly. "
                        "Provide a concise 2-3 sentence summary of ONLY what was actually said in the transcript. "
                        "Do NOT invent, assume, or hallucinate any details not explicitly present in the transcript. "
                        "If the transcript is unclear, short, or mostly silence, just say "
                        "'Supervisor spoke briefly with the customer' — do NOT fabricate specifics. "
                        "Only mention resolutions or commitments if they are EXPLICITLY stated in the transcript."
                    ),
                },
                {"role": "user", "content": f"Exact conversation transcript:\n\n{transcript}"},
            ],
            max_tokens=200,
        )
        summary = response.choices[0].message.content.strip()
        print(f"[summarize] Result: {summary}")
        return summary
    except Exception as e:
        print(f"[summarize] GPT-4o error: {e}")
        return "Supervisor spoke with the customer and addressed their concerns."


# ── Entry Point ──────────────────────────────────────────────────────────────

@app.on_event("startup")
async def configure_twiml_app():
    """Auto-configure TwiML App Voice URL on startup so barge works."""
    twiml_app_sid = os.environ.get("TWILIO_TWIML_APP_SID")
    public_domain = os.environ.get("TWILIO_VOICE_PUBLIC_DOMAIN")
    if not twiml_app_sid or not public_domain:
        print("[STARTUP] Skipping TwiML App config — missing TWILIO_TWIML_APP_SID or TWILIO_VOICE_PUBLIC_DOMAIN")
        return
    try:
        from twilio.rest import Client
        client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        voice_url = f"https://{public_domain}/voice-outgoing"
        client.applications(twiml_app_sid).update(
            voice_url=voice_url,
            voice_method="POST",
        )
        print(f"[STARTUP] TwiML App {twiml_app_sid} Voice URL set to {voice_url}")
    except Exception as e:
        print(f"[STARTUP] Failed to update TwiML App: {e}")


if __name__ == "__main__":
    print("\n  Twilio Observe — Camping World Agent")
    print(f"  Dashboard: http://localhost:{server.config.port}/dashboard")
    print(f"  React UI:  http://localhost:5173")
    print(f"  Health:    http://localhost:{server.config.port}/health\n")
    server.start()
