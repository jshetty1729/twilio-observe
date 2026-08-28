import logging

from fastapi import APIRouter

from twilio_observe.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/token/sync")
async def get_sync_token():
    if not settings.twilio_account_sid or not settings.twilio_api_key:
        return {"token": "mock-sync-token-local-dev"}

    try:
        from twilio.jwt.access_token import AccessToken
        from twilio.jwt.access_token.grants import SyncGrant

        token = AccessToken(
            settings.twilio_account_sid,
            settings.twilio_api_key,
            settings.twilio_api_secret,
            identity="supervisor",
        )
        sync_grant = SyncGrant(service_sid=settings.twilio_sync_service_sid)
        token.add_grant(sync_grant)
        return {"token": token.to_jwt()}
    except Exception as e:
        logger.error(f"Failed to generate Sync token: {e}")
        return {"token": "mock-sync-token-error"}


@router.get("/api/token/voice")
async def get_voice_token():
    if not settings.twilio_account_sid or not settings.twilio_api_key:
        return {"token": "mock-voice-token-local-dev"}

    try:
        from twilio.jwt.access_token import AccessToken
        from twilio.jwt.access_token.grants import VoiceGrant

        token = AccessToken(
            settings.twilio_account_sid,
            settings.twilio_api_key,
            settings.twilio_api_secret,
            identity="supervisor",
        )
        voice_grant = VoiceGrant(
            outgoing_application_sid=settings.twilio_twiml_app_sid,
            incoming_allow=True,
        )
        token.add_grant(voice_grant)
        return {"token": token.to_jwt()}
    except Exception as e:
        logger.error(f"Failed to generate Voice token: {e}")
        return {"token": "mock-voice-token-error"}
