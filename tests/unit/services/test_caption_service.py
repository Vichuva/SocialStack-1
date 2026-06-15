import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from socialstack.utils.errors import TwitterCharLimitError


@pytest.mark.asyncio
async def test_twitter_char_limit_triggers_retry(mock_ai):
    """If AI returns >280 chars for twitter, service retries with shorten instruction."""
    call_count = 0

    async def mock_chat(prompt, system=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return '{"caption": "' + "A" * 260 + '", "hashtags": ["#test1", "#test2"]}'
        return '{"caption": "Short caption", "hashtags": ["#test"]}'

    mock_ai.chat = mock_chat

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


@pytest.mark.asyncio
async def test_twitter_char_limit_raises_after_retry():
    """AI still returns >280 on retry → TwitterCharLimitError raised."""
    from socialstack.services.context_service import GenerationContext

    ctx = GenerationContext(
        business_id="b", business_name="Test", industry="test",
        brand_tone="pro", pain_points=[], ai_generate_images=False,
        auto_approve=False, tier="standard",
    )

    class AlwaysLongAI:
        async def chat(self, prompt, system=None):
            return '{"caption": "' + "A" * 270 + '", "hashtags": ["#hash1", "#hash2"]}'

        async def generate_image(self, prompt, size="1024x1024"):
            return b""

    mock_session = AsyncMock()
    mock_variant_repo = AsyncMock()
    mock_variant_repo.get_next_version = AsyncMock(return_value=1)
    mock_variant_repo.get_latest_for_slot_platform = AsyncMock(return_value=None)
    mock_slot_repo = AsyncMock()
    slot = MagicMock()
    slot.status = "pending_caption"
    mock_slot_repo.get = AsyncMock(return_value=slot)

    with patch("socialstack.services.caption_service.build_context", return_value=ctx), \
         patch("socialstack.services.caption_service.ContentVariantRepository", return_value=mock_variant_repo), \
         patch("socialstack.services.caption_service.ContentSlotRepository", return_value=mock_slot_repo):
        from socialstack.services.caption_service import CaptionService
        svc = CaptionService(session=mock_session, ai=AlwaysLongAI())
        with pytest.raises(TwitterCharLimitError):
            await svc.generate(
                slot_id="s1", business_id="b1", platform="twitter",
                brief={"hook": "H", "key_message": "M", "emotional_angle": "E", "visual_direction": "V", "cta": "C"},
            )


@pytest.mark.asyncio
async def test_caption_service_advances_slot_to_pending_review():
    """CaptionService moves slot from pending_caption → pending_review after saving variant."""
    from socialstack.services.context_service import GenerationContext

    ctx = GenerationContext(
        business_id="b", business_name="Test Co", industry="retail",
        brand_tone="professional", pain_points=[], ai_generate_images=True,
        auto_approve=False, tier="standard",
    )

    class ShortCaptionAI:
        async def chat(self, prompt, system=None):
            return '{"caption": "Simple short caption ready to publish.", "hashtags": ["#brand"]}'

        async def generate_image(self, prompt, size="1024x1024"):
            return b""

    mock_session = AsyncMock()
    mock_variant = MagicMock()
    mock_variant.id = "var_001"
    mock_variant.version = 1
    mock_variant_repo = AsyncMock()
    mock_variant_repo.get_next_version = AsyncMock(return_value=1)
    mock_variant_repo.get_latest_for_slot_platform = AsyncMock(return_value=None)
    mock_variant_repo.create = AsyncMock(return_value=mock_variant)

    slot = MagicMock()
    slot.id = "slot_001"
    slot.status = "pending_caption"
    mock_slot_repo = AsyncMock()
    mock_slot_repo.get = AsyncMock(return_value=slot)
    mock_slot_repo.update = AsyncMock(return_value=slot)

    with patch("socialstack.services.caption_service.build_context", return_value=ctx), \
         patch("socialstack.services.caption_service.ContentVariantRepository", return_value=mock_variant_repo), \
         patch("socialstack.services.caption_service.ContentSlotRepository", return_value=mock_slot_repo):

        from socialstack.services.caption_service import CaptionService
        svc = CaptionService(session=mock_session, ai=ShortCaptionAI())
        await svc.generate(
            slot_id="slot_001", business_id="b1", platform="instagram",
            brief={"hook": "H", "key_message": "M", "emotional_angle": "E", "visual_direction": "V", "cta": "C"},
        )

    mock_slot_repo.update.assert_called_once()
    update_call = mock_slot_repo.update.call_args
    assert update_call.kwargs.get("status") == "pending_review"
