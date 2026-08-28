import json
import logging

from fastapi import APIRouter, Form, Response

from twilio_observe.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/calls/inbound")
async def inbound_call(CallSid: str = Form(""), From: str = Form("")):
    logger.info(f"Inbound call: {CallSid} from {From}")

    ws_url = settings.ngrok_url.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = f"{ws_url}/ws/relay/{CallSid}"

    ci_attr = ""
    if settings.twilio_ci_service_sid:
        ci_attr = f'\n      intelligenceService="{settings.twilio_ci_service_sid}"'

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect action="{settings.ngrok_url}/api/calls/connect-action">
    <ConversationRelay
      url="{ws_url}"
      voice="en-US-Journey-O"
      ttsProvider="Google"
      transcriptionProvider="Deepgram"
      welcomeGreeting="Welcome to Camping World! I'm here to help you with product information, trade-in estimates, and appointment scheduling. What can I help you with today?"
      interruptible="speech"{ci_attr}
    />
  </Connect>
</Response>"""

    return Response(content=twiml, media_type="text/xml")


@router.post("/api/calls/connect-action")
async def connect_action(CallSid: str = Form(""), HandoffData: str = Form("")):
    logger.info(f"Connect action for {CallSid}")

    handoff = {}
    if HandoffData:
        try:
            handoff = json.loads(HandoffData)
        except (json.JSONDecodeError, TypeError):
            pass

    if handoff.get("reason") == "barge":
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial>
    <Conference statusCallback="{settings.ngrok_url}/api/calls/conference-status" statusCallbackEvent="join leave end">{CallSid}-conference</Conference>
  </Dial>
</Response>"""
    else:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Hangup/>
</Response>"""

    return Response(content=twiml, media_type="text/xml")


@router.post("/api/calls/conference-status")
async def conference_status(
    ConferenceSid: str = Form(""),
    StatusCallbackEvent: str = Form(""),
    CallSid: str = Form(""),
):
    logger.info(f"Conference {ConferenceSid}: {StatusCallbackEvent} - {CallSid}")
    return {"ok": True}
