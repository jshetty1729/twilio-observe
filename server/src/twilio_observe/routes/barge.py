"""
Barge API — TAC-style barge with conference redirect.

Flow:
1. POST /api/barge/initiate — set barge_active, redirect customer to Conference, return voice token
2. POST /api/barge/hand-back — clear barge_active, redirect customer back to TAC webhook with history
"""

import os
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from twilio_observe.session_store import store
from twilio_observe.relay.handler import barge_active, build_conversation
from twilio_observe.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class BargeRequest(BaseModel):
    callSid: str


@router.post("/api/barge/initiate")
async def barge_initiate(req: BargeRequest):
    session = store.get(req.callSid)
    if session is None:
        raise HTTPException(status_code=404, detail="No active session for this call")

    # Set barge flag — relay handler will suppress AI audio
    barge_active[req.callSid] = True
    session.status = "barged"
    conf_name = f"barge-{req.callSid}"

    store.add_turn(req.callSid, "supervisor", "[BARGE] Supervisor has taken over the conversation.")

    # Redirect customer call to conference (requires Twilio client)
    redirect_success = False
    try:
        from twilio.rest import Client
        from twilio.jwt.access_token import AccessToken
        from twilio.jwt.access_token.grants import VoiceGrant

        if settings.twilio_account_sid and settings.twilio_auth_token:
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            client.calls(req.callSid).update(
                twiml=f'<Response><Conference>{conf_name}</Conference></Response>'
            )
            redirect_success = True
    except ImportError:
        logger.warning("twilio SDK not installed — skipping conference redirect")
    except Exception as e:
        logger.error(f"Conference redirect failed: {e}")

    # Generate capability token for supervisor Voice JS SDK
    token_jwt = None
    try:
        from twilio.jwt.access_token import AccessToken
        from twilio.jwt.access_token.grants import VoiceGrant

        if settings.twilio_api_key and settings.twilio_api_secret:
            token = AccessToken(
                settings.twilio_account_sid,
                settings.twilio_api_key,
                settings.twilio_api_secret,
                identity="supervisor",
            )
            token.add_grant(VoiceGrant(
                outgoing_application_sid=settings.twilio_twiml_app_sid or None,
                incoming_allow=True,
            ))
            token_jwt = token.to_jwt()
    except Exception as e:
        logger.error(f"Token generation failed: {e}")

    return {
        "status": "barged",
        "callSid": req.callSid,
        "confName": conf_name,
        "redirected": redirect_success,
        "token": token_jwt,
    }


@router.post("/api/barge/hand-back")
async def barge_hand_back(req: BargeRequest):
    session = store.get(req.callSid)
    if session is None:
        raise HTTPException(status_code=404, detail="No active session for this call")

    # Clear barge flag — AI resumes responding
    barge_active[req.callSid] = False
    session.status = "active"

    store.add_turn(req.callSid, "supervisor", "[HAND BACK] AI agent reactivated.")

    # Redirect customer back to TAC/ConversationRelay webhook with history context
    redirect_success = False
    try:
        from twilio.rest import Client

        if settings.twilio_account_sid and settings.twilio_auth_token:
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

            # Build resume context — summarize last 10 turns
            conversation = build_conversation(req.callSid)
            history_summary = "\n".join(
                f"{m['role'].upper()}: {m['content']}"
                for m in conversation[-10:]
            )

            # Store resume context for the new CR session
            session.resume_context = history_summary

            # Redirect back to voice webhook (starts new CR session with context)
            resume_url = f"{settings.ngrok_url}/api/calls/inbound?resume_context={req.callSid}"
            client.calls(req.callSid).update(url=resume_url)
            redirect_success = True
    except ImportError:
        logger.warning("twilio SDK not installed — skipping redirect")
    except Exception as e:
        logger.error(f"Hand-back redirect failed: {e}")

    return {
        "status": "hand_back_complete",
        "callSid": req.callSid,
        "redirected": redirect_success,
    }
