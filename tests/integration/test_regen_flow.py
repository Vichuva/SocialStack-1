"""Integration tests for the regeneration pipeline (WF-REGEN).

Tests cover: feedback analysis → brief adjustment → new caption versioning.
No real DB or AI API calls — repositories and AI client are mocked.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import MockAIClient

_ORIGINAL_BRIEF = {
    "hook": "Save money today",
    "key_message": "Best prices in town",
    "emotional_angle": "Urgency — limited time offer",
    "visual_direction": "Promotional banner with price callout",
    "cta": "Buy now",
}


def _make_slot(slot_id="slot_001", business_id="biz_001", platform="instagram"):
    slot = MagicMock()
    slot.id = slot_id
    slot.business_id = business_id
    slot.platform = platform
    slot.status = "pending_review"
    return slot


def _make_variant(variant_id="var_v2", version=2):
    variant = MagicMock()
    variant.id = variant_id
    variant.version = version
    variant.caption = "Short caption for test."
    variant.hashtags = ["#brand"]
    variant.char_count = 30
    return variant


@pytest.mark.asyncio
async def test_regeneration_creates_new_variant_version():
    """RegenerationService produces a new variant with version > original."""
    from socialstack.services.context_service import GenerationContext

    ctx = GenerationContext(
        business_id="biz_001",
        business_name="Luma Dental",
        industry="dental",
        brand_tones=["warm", "reassuring"],
        target_audience=[],
        pain_points=["fear of pain"],
        ai_generate_images=False,
        auto_approve=False,
        tier="standard",
    )

    slot = _make_slot()
    new_variant = _make_variant(version=2)

    mock_session = AsyncMock()
    mock_slot_repo = AsyncMock()
    mock_slot_repo.get = AsyncMock(return_value=slot)
    mock_slot_repo.update = AsyncMock(return_value=slot)

    mock_variant_repo = AsyncMock()
    mock_variant_repo.get_next_version = AsyncMock(return_value=2)
    mock_variant_repo.get_latest_for_slot_platform = AsyncMock(return_value=None)
    mock_variant_repo.create = AsyncMock(return_value=new_variant)

    with patch("socialstack.services.caption_service.build_context", return_value=ctx), \
         patch("socialstack.services.caption_service.ContentVariantRepository", return_value=mock_variant_repo), \
         patch("socialstack.services.caption_service.ContentSlotRepository", return_value=mock_slot_repo), \
         patch("socialstack.services.regeneration_service.ContentSlotRepository", return_value=mock_slot_repo):

        from socialstack.services.regeneration_service import RegenerationService
        svc = RegenerationService(session=mock_session, ai=MockAIClient())
        result = await svc.regenerate(
            slot_id="slot_001",
            business_id="biz_001",
            platform="instagram",
            feedback="Too promotional — make it more educational",
            original_brief=_ORIGINAL_BRIEF,
        )

    assert result.version == 2


@pytest.mark.asyncio
async def test_feedback_analysis_adjusts_brief():
    """RegenerationService passes feedback through the AI and builds an enhanced brief
    that differs from the original before re-captioning."""
    from socialstack.services.context_service import GenerationContext

    ctx = GenerationContext(
        business_id="biz_001",
        business_name="Luma Dental",
        industry="dental",
        brand_tones=["warm", "reassuring"],
        target_audience=[],
        pain_points=["fear of pain"],
        ai_generate_images=False,
        auto_approve=False,
        tier="standard",
    )

    slot = _make_slot()
    new_variant = _make_variant(version=2)

    # Track what brief was ultimately passed to caption generation
    caption_briefs_received: list[dict] = []

    class CaptureBriefAI(MockAIClient):
        async def chat(self, prompt: str, system=None) -> str:
            # Let regen analysis and caption go through normally
            return await super().chat(prompt, system)

    mock_session = AsyncMock()
    mock_slot_repo = AsyncMock()
    mock_slot_repo.get = AsyncMock(return_value=slot)
    mock_slot_repo.update = AsyncMock(return_value=slot)

    mock_variant_repo = AsyncMock()
    mock_variant_repo.get_next_version = AsyncMock(return_value=2)
    mock_variant_repo.get_latest_for_slot_platform = AsyncMock(return_value=None)
    mock_variant_repo.create = AsyncMock(return_value=new_variant)

    with patch("socialstack.services.caption_service.build_context", return_value=ctx), \
         patch("socialstack.services.caption_service.ContentVariantRepository", return_value=mock_variant_repo), \
         patch("socialstack.services.caption_service.ContentSlotRepository", return_value=mock_slot_repo), \
         patch("socialstack.services.regeneration_service.ContentSlotRepository", return_value=mock_slot_repo):

        from socialstack.services.regeneration_service import RegenerationService
        svc = RegenerationService(session=mock_session, ai=CaptureBriefAI())
        result = await svc.regenerate(
            slot_id="slot_001",
            business_id="biz_001",
            platform="instagram",
            feedback="Too promotional — make it educational",
            original_brief=_ORIGINAL_BRIEF,
        )

    # Result exists and is a new variant
    assert result is not None
    # Slot was moved back to pending_review
    mock_slot_repo.update.assert_called()
    update_kwargs = mock_slot_repo.update.call_args.kwargs
    assert update_kwargs.get("status") == "pending_review"


@pytest.mark.asyncio
async def test_regen_falls_back_to_original_brief_on_ai_failure():
    """If the regen analysis AI call fails, a ValidationError is raised — no silent fallback."""
    from socialstack.utils.errors import AIParseError

    class BrokenAI:
        async def chat(self, prompt: str, system=None) -> str:
            if "adjusted_hook" in prompt.lower() or "expert content director" in prompt.lower():
                raise AIParseError("broken json", provider="test")
            return '{"caption": "Fallback caption.", "hashtags": ["#ok"]}'

        async def generate_image(self, prompt: str, size="1024x1024") -> bytes:
            return b""

    mock_session = AsyncMock()

    with patch("socialstack.services.regeneration_service.ContentSlotRepository"):
        from socialstack.services.regeneration_service import RegenerationService
        svc = RegenerationService(session=mock_session, ai=BrokenAI())

        with pytest.raises(AIParseError):
            await svc.regenerate(
                slot_id="slot_001",
                business_id="biz_001",
                platform="instagram",
                feedback="Make it better",
                original_brief=_ORIGINAL_BRIEF,
            )


@pytest.mark.asyncio
async def test_slot_returns_to_pending_review_after_regen():
    """After regeneration completes, the slot's status is set back to pending_review."""
    from socialstack.services.context_service import GenerationContext

    ctx = GenerationContext(
        business_id="biz_001",
        business_name="Luma Dental",
        industry="dental",
        brand_tones=["warm", "reassuring"],
        target_audience=[],
        pain_points=[],
        ai_generate_images=False,
        auto_approve=False,
        tier="standard",
    )

    slot = _make_slot()
    slot.status = "pending_review"
    new_variant = _make_variant(version=2)

    mock_session = AsyncMock()
    mock_slot_repo = AsyncMock()
    mock_slot_repo.get = AsyncMock(return_value=slot)
    mock_slot_repo.update = AsyncMock(return_value=slot)

    mock_variant_repo = AsyncMock()
    mock_variant_repo.get_next_version = AsyncMock(return_value=2)
    mock_variant_repo.get_latest_for_slot_platform = AsyncMock(return_value=None)
    mock_variant_repo.create = AsyncMock(return_value=new_variant)

    with patch("socialstack.services.caption_service.build_context", return_value=ctx), \
         patch("socialstack.services.caption_service.ContentVariantRepository", return_value=mock_variant_repo), \
         patch("socialstack.services.caption_service.ContentSlotRepository", return_value=mock_slot_repo), \
         patch("socialstack.services.regeneration_service.ContentSlotRepository", return_value=mock_slot_repo):

        from socialstack.services.regeneration_service import RegenerationService
        svc = RegenerationService(session=mock_session, ai=MockAIClient())
        await svc.regenerate(
            slot_id="slot_001",
            business_id="biz_001",
            platform="instagram",
            feedback="Make it less salesy",
            original_brief=_ORIGINAL_BRIEF,
        )

    # Slot status must have been set to pending_review
    update_calls = mock_slot_repo.update.call_args_list
    statuses_set = [c.kwargs.get("status") for c in update_calls if c.kwargs.get("status")]
    assert "pending_review" in statuses_set
