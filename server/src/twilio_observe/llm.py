from __future__ import annotations

import logging

from openai import AsyncOpenAI

from twilio_observe.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key or None)
    return _client

BASE_SYSTEM_PROMPT = """You are a helpful AI assistant for Camping World, one of America's largest RV and outdoor recreation retailers with over 180 locations. You help customers with:

- Product information about RVs, campers, and outdoor equipment
- Trade-in value estimates — when asked, USE the estimate tool (ask for year, make, model, mileage, condition)
- Appointment scheduling — when asked, book it directly, don't deflect to "our team will reach out"
- General inquiries about services and locations

IMPORTANT RULES:
1. Be proactive and helpful. Never deflect when you can answer directly.
2. If asked about trade-in values, always ask for details and provide an estimate range.
3. If asked to schedule, give specific available times (Saturday 10am or 2pm, weekdays 9am-5pm).
4. Keep responses conversational and concise — this is a phone call, not an email.
5. You represent the specific Camping World location closest to the caller."""


async def generate_response(
    system_prompt: str,
    conversation: list[dict[str, str]],
) -> str:
    messages = [{"role": "system", "content": system_prompt}] + conversation

    try:
        response = await _get_client().chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=150,
            temperature=0.7,
        )
        text = response.choices[0].message.content
        if not text:
            return "I apologize, could you say that again?"
        return text.strip()
    except Exception as e:
        logger.error(f"OpenAI request failed: {e}")
        return "I'm sorry, I'm experiencing a brief technical issue. One moment please."
