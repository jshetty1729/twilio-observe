from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from twilio_observe.llm import generate_response


@pytest.mark.asyncio
async def test_generate_response_returns_text():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "I can help with that!"

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("twilio_observe.llm._get_client", return_value=mock_client):
        result = await generate_response(
            system_prompt="You are a helpful assistant.",
            conversation=[{"role": "user", "content": "Hello"}],
        )
        assert result == "I can help with that!"


@pytest.mark.asyncio
async def test_generate_response_handles_error():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API down"))

    with patch("twilio_observe.llm._get_client", return_value=mock_client):
        result = await generate_response(
            system_prompt="You are a helper.",
            conversation=[{"role": "user", "content": "Hi"}],
        )
        assert "sorry" in result.lower() or "issue" in result.lower()
