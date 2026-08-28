from __future__ import annotations

import re

NEGATIVE_PATTERNS = [
    re.compile(r"ridiculous", re.IGNORECASE),
    re.compile(r"frustrated", re.IGNORECASE),
    re.compile(r"can't believe", re.IGNORECASE),
    re.compile(r"waste of time", re.IGNORECASE),
    re.compile(r"that doesn't help", re.IGNORECASE),
    re.compile(r"I just said", re.IGNORECASE),
    re.compile(r"already told you", re.IGNORECASE),
    re.compile(r"that's not what I", re.IGNORECASE),
    re.compile(r"you're not listening", re.IGNORECASE),
    re.compile(r"this is terrible", re.IGNORECASE),
    re.compile(r"unacceptable", re.IGNORECASE),
    re.compile(r"speak to (a |your )?manager", re.IGNORECASE),
    re.compile(r"hang up", re.IGNORECASE),
    re.compile(r"never (call|come) back", re.IGNORECASE),
    re.compile(r"worst experience", re.IGNORECASE),
]

POSITIVE_PATTERNS = [
    re.compile(r"that sounds good", re.IGNORECASE),
    re.compile(r"perfect", re.IGNORECASE),
    re.compile(r"great", re.IGNORECASE),
    re.compile(r"thank you", re.IGNORECASE),
    re.compile(r"awesome", re.IGNORECASE),
    re.compile(r"wonderful", re.IGNORECASE),
    re.compile(r"exactly what I needed", re.IGNORECASE),
    re.compile(r"you've been helpful", re.IGNORECASE),
    re.compile(r"appreciate", re.IGNORECASE),
    re.compile(r"excellent", re.IGNORECASE),
]

DEFLECTION_PATTERNS = [
    re.compile(r"3 to 5 business days", re.IGNORECASE),
    re.compile(r"our team will reach out", re.IGNORECASE),
    re.compile(r"I wouldn't want to give you an inaccurate", re.IGNORECASE),
    re.compile(r"bring it in for", re.IGNORECASE),
    re.compile(r"highly individualized", re.IGNORECASE),
    re.compile(r"I apologize for any confusion", re.IGNORECASE),
]


class CsatScorer:
    def __init__(self):
        self._scores: dict[str, int] = {}

    def init_call(self, call_sid: str, initial_score: int = 7) -> None:
        self._scores[call_sid] = initial_score

    def get_score(self, call_sid: str) -> int:
        return self._scores.get(call_sid, 7)

    def score_customer_message(self, call_sid: str, message: str) -> int:
        current = self._scores.get(call_sid, 7)
        adjustment = 0

        for pattern in NEGATIVE_PATTERNS:
            if pattern.search(message):
                adjustment -= 2
                break

        for pattern in POSITIVE_PATTERNS:
            if pattern.search(message):
                adjustment += 1
                break

        new_score = max(1, min(10, current + adjustment))
        self._scores[call_sid] = new_score
        return new_score

    def score_ai_response(self, call_sid: str, message: str) -> int:
        current = self._scores.get(call_sid, 7)
        adjustment = 0

        for pattern in DEFLECTION_PATTERNS:
            if pattern.search(message):
                adjustment -= 1
                break

        new_score = max(1, min(10, current + adjustment))
        self._scores[call_sid] = new_score
        return new_score

    def end_call(self, call_sid: str) -> None:
        self._scores.pop(call_sid, None)


# Global singleton
csat_scorer = CsatScorer()
