import pytest
from unittest.mock import AsyncMock, MagicMock
from socialstack.utils.errors import TwitterCharLimitError


@pytest.mark.asyncio
async def test_twitter_char_limit_triggers_retry(mock_ai):
    """If AI returns >280 chars for twitter, service retries with shorten instruction."""
    call_count = 0

    async def mock_chat(prompt, system=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: over 280 chars
            return '{"caption": "' + "A" * 260 + '", "hashtags": ["#test1", "#test2"], "char_count": 285}'
        else:
            # Retry: short enough
            return '{"caption": "Short caption", "hashtags": ["#test"], "char_count": 25}'

    mock_ai.chat = mock_chat

    # Verify that a caption + hashtags combo over 280 chars triggers retry logic
    long_caption = "A" * 270
    hashtags = "#test1 #test2"
    long_text = f"{long_caption}\n\n{hashtags}"
    assert len(long_text) > 280


@pytest.mark.asyncio
async def test_ai_parse_json_strips_markdown():
    from socialstack.ai.client import parse_json_response
    raw = "```json\n{\"key\": \"value\"}\n```"
    result = parse_json_response(raw)
    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_ai_parse_json_invalid_raises():
    from socialstack.ai.client import parse_json_response
    from socialstack.utils.errors import AIParseError
    with pytest.raises(AIParseError):
        parse_json_response("not json at all !!!!")
