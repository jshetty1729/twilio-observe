"""
VoiceChannel — manages ConversationRelay WebSocket lifecycle.

Mirrors TAC SDK's VoiceChannel which:
- Accepts WebSocket connections from Twilio ConversationRelay
- Parses setup/prompt/interrupt messages from Twilio
- Sends text/end/dtmf messages to Twilio
- Fires on_message_ready callback for each customer utterance
- Integrates with LLM adapter for response generation
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from fastapi import WebSocket

from twilio_observe.tac.conversation_session import ConversationSession, session_manager

logger = logging.getLogger(__name__)

# Type alias for the on_message_ready callback
MessageReadyCallback = Callable[
    ["VoiceChannel", ConversationSession, str], Awaitable[str | None]
]


@dataclass
class VoiceChannelConfig:
    """Configuration for VoiceChannel behavior."""

    system_prompt: str = ""
    voice: str = "Google.en-US-Journey-F"
    language: str = "en-US"
    tts_provider: str = "google"
    transcription_provider: str = "google"
    speech_model: str = "telephony"
    profanity_filter: bool = False
    dtmf_detection: bool = True
    interruptible: bool = True
    welcome_greeting: str = ""


class VoiceChannel:
    """
    Manages a single ConversationRelay WebSocket connection.

    Usage:
        channel = VoiceChannel(config=VoiceChannelConfig(...))

        @channel.on_message_ready
        async def handle_message(channel, session, text):
            response = await llm.generate(text, session)
            return response

        # In WebSocket route:
        await channel.handle_connection(websocket, call_sid)
    """

    def __init__(self, config: VoiceChannelConfig | None = None) -> None:
        self.config = config or VoiceChannelConfig()
        self._on_message_ready: MessageReadyCallback | None = None
        self._on_setup: Callable[[ConversationSession, dict], Awaitable[None]] | None = None
        self._on_disconnect: Callable[[ConversationSession], Awaitable[None]] | None = None
        self._ws: WebSocket | None = None
        self._session: ConversationSession | None = None

    def on_message_ready(self, callback: MessageReadyCallback) -> MessageReadyCallback:
        """Decorator to register the message handler."""
        self._on_message_ready = callback
        return callback

    def on_setup(self, callback: Callable[[ConversationSession, dict], Awaitable[None]]) -> None:
        self._on_setup = callback

    def on_disconnect(self, callback: Callable[[ConversationSession], Awaitable[None]]) -> None:
        self._on_disconnect = callback

    async def handle_connection(self, ws: WebSocket, call_sid: str) -> None:
        """Main WebSocket lifecycle handler."""
        await ws.accept()
        self._ws = ws
        self._session = session_manager.create(call_sid)

        try:
            async for raw_message in ws.iter_text():
                await self._process_message(raw_message)
        except Exception as e:
            logger.error(f"WebSocket error for {call_sid}: {e}")
        finally:
            session_manager.end(call_sid)
            if self._on_disconnect and self._session:
                await self._on_disconnect(self._session)
            self._ws = None
            self._session = None

    async def _process_message(self, raw: str) -> None:
        """Route incoming ConversationRelay messages."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from ConversationRelay: {raw[:100]}")
            return

        msg_type = msg.get("type")

        if msg_type == "setup":
            await self._handle_setup(msg)
        elif msg_type == "prompt":
            await self._handle_prompt(msg)
        elif msg_type == "interrupt":
            await self._handle_interrupt(msg)
        elif msg_type == "dtmf":
            logger.info(f"DTMF received: {msg.get('digit')}")
        else:
            logger.debug(f"Unknown message type: {msg_type}")

    async def _handle_setup(self, msg: dict) -> None:
        """Handle setup message — connection established."""
        if self._session:
            self._session.from_number = msg.get("from", "")
            if self._on_setup:
                await self._on_setup(self._session, msg)

        # Send welcome greeting if configured
        if self.config.welcome_greeting:
            await self.send_text(self.config.welcome_greeting)

    async def _handle_prompt(self, msg: dict) -> None:
        """Handle prompt message — customer spoke."""
        text = msg.get("voicePrompt", "")
        if not text or not self._session:
            return

        # Record customer turn
        self._session.add_turn("customer", text)

        # Fire on_message_ready callback
        if self._on_message_ready:
            response = await self._on_message_ready(self, self._session, text)
            if response:
                # Record agent turn and send response
                self._session.add_turn("agent", response)
                await self.send_text(response)

    async def _handle_interrupt(self, msg: dict) -> None:
        """Handle interrupt — customer interrupted agent speech."""
        logger.debug(f"Speech interrupted: {msg.get('utteranceUntilInterrupt', '')}")

    async def send_text(self, text: str) -> None:
        """Send text response to ConversationRelay (TTS)."""
        if self._ws:
            await self._ws.send_json({"type": "text", "token": text, "last": True})

    async def send_tokens(self, token: str, last: bool = False) -> None:
        """Send streaming token to ConversationRelay."""
        if self._ws:
            await self._ws.send_json({"type": "text", "token": token, "last": last})

    async def send_end(self) -> None:
        """End the ConversationRelay session (triggers connect-action callback)."""
        if self._ws:
            await self._ws.send_json({"type": "end"})

    @property
    def session(self) -> ConversationSession | None:
        return self._session
