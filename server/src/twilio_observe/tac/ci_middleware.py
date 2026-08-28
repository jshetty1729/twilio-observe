"""
CIEventCaptureMiddleware — captures Conversation Intelligence webhook events.

Mirrors TAC SDK's CIEventCaptureMiddleware which:
- Exposes a POST endpoint for CI webhook callbacks
- Parses operator results (sentiment, topic, CSAT prediction)
- Attaches results to the corresponding ConversationSession.metadata
- Fires registered callbacks when new CI data arrives
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Request

from twilio_observe.tac.conversation_session import session_manager

logger = logging.getLogger(__name__)

CIEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class CIEventCaptureMiddleware:
    """
    Captures Conversation Intelligence webhook events and attaches
    them to the relevant ConversationSession.

    Usage:
        ci_middleware = CIEventCaptureMiddleware()

        @ci_middleware.on_event
        async def handle_ci(call_sid, results):
            print(f"CI results for {call_sid}: {results}")

        app.include_router(ci_middleware.router)
    """

    def __init__(self, path: str = "/ci-webhook") -> None:
        self.router = APIRouter()
        self._callbacks: list[CIEventCallback] = []
        self._path = path
        self.ci_events: dict[str, list[dict]] = {}

        self.router.add_api_route(
            self._path, self._handle_webhook, methods=["POST"]
        )

    def on_event(self, callback: CIEventCallback) -> CIEventCallback:
        """Decorator to register a CI event handler."""
        self._callbacks.append(callback)
        return callback

    async def _handle_webhook(self, request: Request) -> dict:
        """Handle incoming CI webhook POST from Twilio."""
        body = await request.json()

        call_sid = body.get("call_sid") or body.get("CallSid") or body.get("conversationId", "")
        operator_results = body.get("operator_results") or body.get("operatorResults", {})
        transcript_sid = body.get("transcript_sid", "")

        logger.info(f"CI webhook received for call {call_sid}")

        # Store in ci_events dict (keyed by conversation/call ID)
        self.ci_events.setdefault(call_sid, []).append({
            "transcript_sid": transcript_sid,
            "operators": operator_results,
            "raw": body,
        })

        # Attach to session metadata
        session = session_manager.get(call_sid)
        if session:
            session.metadata["ci_results"] = self.ci_events[call_sid]

            # Extract specific operator values
            if "sentiment" in operator_results:
                session.metadata["ci_sentiment"] = operator_results["sentiment"]
            if "topic_detection" in operator_results:
                session.metadata["ci_topics"] = operator_results["topic_detection"]
            if "predictive_csat" in operator_results:
                ci_csat = operator_results["predictive_csat"]
                session.metadata["ci_csat"] = ci_csat
                # Override heuristic CSAT with authoritative CI score
                if isinstance(ci_csat, dict) and "score" in ci_csat:
                    session.metadata["csat_score"] = ci_csat["score"]

        # Fire callbacks
        for cb in self._callbacks:
            try:
                await cb(call_sid, operator_results)
            except Exception as e:
                logger.error(f"CI callback error: {e}")

        return {"status": "received", "call_sid": call_sid}

    def get_events(self, call_sid: str) -> list[dict]:
        """Get all CI events for a given call/conversation."""
        return self.ci_events.get(call_sid, [])
