from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class CallSession:
    call_sid: str
    caller_number: str
    start_time: float = field(default_factory=time.time)
    status: str = "active"  # active | coached | barged | completed
    csat: int = 7
    topic: str = ""
    transcript: list[dict] = field(default_factory=list)
    coaching_instructions: list[str] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)
    resume_context: str = ""


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, CallSession] = {}

    def create(self, call_sid: str, caller_number: str) -> CallSession:
        session = CallSession(call_sid=call_sid, caller_number=caller_number)
        self._sessions[call_sid] = session
        return session

    def get(self, call_sid: str) -> CallSession | None:
        return self._sessions.get(call_sid)

    def get_all_active(self) -> list[CallSession]:
        return [s for s in self._sessions.values() if s.status != "completed"]

    def add_turn(self, call_sid: str, role: str, content: str) -> None:
        session = self._sessions.get(call_sid)
        if session is None:
            return
        session.transcript.append(
            {
                "id": f"{role}-{int(time.time() * 1000)}",
                "timestamp": int(time.time() * 1000),
                "role": role,
                "content": content,
            }
        )


# Global singleton
store = SessionStore()
