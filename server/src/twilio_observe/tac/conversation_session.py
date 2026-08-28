"""
ConversationSession — per-call state container with metadata.

Mirrors TAC SDK's ConversationSession which stores:
- Call metadata (call_sid, from_number, start_time)
- Transcript turns
- Coaching instructions queue
- Arbitrary metadata dict (CSAT score, topic, alerts, CI results)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TranscriptTurn:
    role: str  # "agent" | "customer"
    text: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConversationSession:
    call_sid: str
    from_number: str = ""
    start_time: float = field(default_factory=time.time)
    transcript: list[TranscriptTurn] = field(default_factory=list)
    coaching_queue: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "active"  # "active" | "barged" | "ended"

    @property
    def duration_seconds(self) -> int:
        return int(time.time() - self.start_time)

    @property
    def csat_score(self) -> float:
        return self.metadata.get("csat_score", 5.0)

    @csat_score.setter
    def csat_score(self, value: float) -> None:
        self.metadata["csat_score"] = value

    @property
    def alerts(self) -> list[dict]:
        return self.metadata.get("alerts", [])

    def add_alert(self, alert_type: str, message: str) -> None:
        if "alerts" not in self.metadata:
            self.metadata["alerts"] = []
        self.metadata["alerts"].append(
            {"type": alert_type, "message": message, "timestamp": time.time()}
        )

    def add_turn(self, role: str, text: str) -> TranscriptTurn:
        turn = TranscriptTurn(role=role, text=text)
        self.transcript.append(turn)
        return turn

    def pop_coaching(self) -> str | None:
        if self.coaching_queue:
            return self.coaching_queue.pop(0)
        return None

    def to_dict(self) -> dict:
        return {
            "call_sid": self.call_sid,
            "from_number": self.from_number,
            "start_time": self.start_time,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "transcript": [
                {"role": t.role, "text": t.text, "timestamp": t.timestamp}
                for t in self.transcript
            ],
            "metadata": self.metadata,
        }


class SessionManager:
    """Manages all active ConversationSessions. Singleton pattern."""

    def __init__(self) -> None:
        self._sessions: dict[str, ConversationSession] = {}
        self._on_session_start: list[Callable[[ConversationSession], None]] = []
        self._on_session_end: list[Callable[[ConversationSession], None]] = []

    def create(self, call_sid: str, from_number: str = "") -> ConversationSession:
        session = ConversationSession(call_sid=call_sid, from_number=from_number)
        self._sessions[call_sid] = session
        for cb in self._on_session_start:
            cb(session)
        return session

    def get(self, call_sid: str) -> ConversationSession | None:
        return self._sessions.get(call_sid)

    def end(self, call_sid: str) -> ConversationSession | None:
        session = self._sessions.get(call_sid)
        if session:
            session.status = "ended"
            for cb in self._on_session_end:
                cb(session)
        return session

    def active_sessions(self) -> list[ConversationSession]:
        return [s for s in self._sessions.values() if s.status != "ended"]

    def all_sessions(self) -> list[ConversationSession]:
        return list(self._sessions.values())

    def on_session_start(self, callback: Callable[[ConversationSession], None]) -> None:
        self._on_session_start.append(callback)

    def on_session_end(self, callback: Callable[[ConversationSession], None]) -> None:
        self._on_session_end.append(callback)


# Global singleton
session_manager = SessionManager()
