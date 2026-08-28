"""
TAC (Twilio Agent Connect) compatibility layer.

Mirrors the patterns from twilio-agent-connect-python SDK:
- VoiceChannel: manages ConversationRelay WebSocket lifecycle
- ConversationSession: per-call state with metadata
- CIEventCaptureMiddleware: captures Conversation Intelligence webhook events
- on_message_ready callback: hook for message processing

When the official SDK is published, replace this module with:
    pip install twilio-agent-connect
"""

from twilio_observe.tac.voice_channel import VoiceChannel, VoiceChannelConfig
from twilio_observe.tac.conversation_session import ConversationSession, SessionManager
from twilio_observe.tac.ci_middleware import CIEventCaptureMiddleware

__all__ = [
    "VoiceChannel",
    "VoiceChannelConfig",
    "ConversationSession",
    "SessionManager",
    "CIEventCaptureMiddleware",
]
