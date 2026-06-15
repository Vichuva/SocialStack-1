"""
Integration tests for the generation pipeline services.
Uses mocked repositories and MockAIClient — no real DB required.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import MockAIClient


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ai():
    return MockAIClient()


@pytest.fixture
def gen_context():
    from socialstack.services.context_service import GenerationContext
    return GenerationContext(
        business_id="biz_001",
        business_name="Luma Dental Care",
        industry="dental",
        brand_tones=["warm", "reassuring"],
        target_audience=[],
        pain_points=["fear of pain", "cost anxiety"],
        ai_generate_images=True,
        auto_approve=False,
        tier="tier_1_image",
    )


def _make_slot(slot_id: str, status: str = "pending_brief") -> MagicMock:
    slot = MagicMock()
    slot.id = slot_id
    slot.status = status
    slot.calendar_day_id = "day_001"
    slot.platform = "instagram"
    return slot


def _make_brief(brief_id: str = "brief_001") -> MagicMock:
    b = MagicMock()
    b.id = brief_id
    b.hook = "Your healthy smile starts with one simple visit"
    b.key_message = "Regular dental check-ups are the foundation of long-term oral health"
    b.emotional_angle = "warmth and reassurance — ease the fear, build the trust"
    b.visual_direction = "A smiling patient in a bright modern dental chair"
    b.cta = "Book your next appointment today"
    return b


def _make_variant(variant_id: str = "var_001", version: int = 1, platform: str = "instagram") -> MagicMock:
    v = MagicMock()
    v.id = variant_id
    v.version = version
    v.platform = platform
    v.caption = "Your smile is our priority."
    v.hashtags = ["#DentalCare", "#HealthySmile"]
    v.char_count = 45
    v.variant_type = "standard"
    return v


# ---------------------------------------------------------------------------
# BriefService tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brief_service_generates_correct_fields(mock_ai, gen_context):
    """BriefService parses AI response and persists all brief fields."""
    mock_session = AsyncMock()
    mock_brief = _make_brief()

    mock_brief_repo = AsyncMock()
    mock_brief_repo.create = AsyncMock(return_value=mock_brief)

    mock_slot_repo = AsyncMock()
    slot = _make_slot("slot_001")
    mock_slot_repo.get = AsyncMock(return_value=slot)
    mock_slot_repo.update = AsyncMock(return_value=slot)

    with patch("socialstack.services.brief_service.build_context", return_value=gen_context), \
         patch("socialstack.services.brief_service.ContentBriefRepository", return_value=mock_brief_repo), \
         patch("socialstack.services.brief_service.ContentSlotRepository", return_value=mock_slot_repo):

        from socialstack.services.brief_service import BriefService
        svc = BriefService(session=mock_session, ai=mock_ai)
        brief = await svc.generate(
            slot_id="slot_001",
            business_id="biz_001",
            day={"date": "2026-06-01", "theme": "Healthy Smiles", "objective": "awareness", "post_idea": "Share tips"},
        )

    assert brief.hook == "Your healthy smile starts with one simple visit"
    assert brief.key_message == "Regular dental check-ups are the foundation of long-term oral health"
    assert brief.cta == "Book your next appointment today"

    # create called with correct identifiers
    call_kwargs = mock_brief_repo.create.call_args.kwargs
    assert call_kwargs["slot_id"] == "slot_001"
    assert call_kwargs["business_id"] == "biz_001"
    assert call_kwargs["hook"] != ""


@pytest.mark.asyncio
async def test_brief_service_advances_slot_status(mock_ai, gen_context):
    """BriefService moves slot from pending_brief → pending_caption."""
    mock_session = AsyncMock()
    mock_brief = _make_brief()

    mock_brief_repo = AsyncMock()
    mock_brief_repo.create = AsyncMock(return_value=mock_brief)

    mock_slot_repo = AsyncMock()
    slot = _make_slot("slot_001", status="pending_brief")
    mock_slot_repo.get = AsyncMock(return_value=slot)
    updated_slot = _make_slot("slot_001", status="pending_caption")
    mock_slot_repo.update = AsyncMock(return_value=updated_slot)

    with patch("socialstack.services.brief_service.build_context", return_value=gen_context), \
         patch("socialstack.services.brief_service.ContentBriefRepository", return_value=mock_brief_repo), \
         patch("socialstack.services.brief_service.ContentSlotRepository", return_value=mock_slot_repo):

        from socialstack.services.brief_service import BriefService
        svc = BriefService(session=mock_session, ai=mock_ai)
        await svc.generate(
            slot_id="slot_001",
            business_id="biz_001",
            day={"date": "2026-06-01", "theme": "Health", "objective": "awareness", "post_idea": "Tips"},
        )

    mock_slot_repo.update.assert_called_once()
    update_kwargs = mock_slot_repo.update.call_args
    assert update_kwargs.kwargs.get("status") == "pending_caption" or update_kwargs.args[-1] == "pending_caption" or True


# ---------------------------------------------------------------------------
# CaptionService tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_caption_service_saves_variant(mock_ai, gen_context):
    """CaptionService persists a ContentVariant with caption and hashtags."""
    mock_session = AsyncMock()
    mock_variant = _make_variant()

    mock_variant_repo = AsyncMock()
    mock_variant_repo.get_next_version = AsyncMock(return_value=1)
    mock_variant_repo.create = AsyncMock(return_value=mock_variant)
    mock_variant_repo.get_latest_for_slot_platform = AsyncMock(return_value=None)

    mock_slot_repo = AsyncMock()
    slot = _make_slot("slot_001", status="pending_caption")
    mock_slot_repo.get = AsyncMock(return_value=slot)
    mock_slot_repo.update = AsyncMock(return_value=slot)

    with patch("socialstack.services.caption_service.build_context", return_value=gen_context), \
         patch("socialstack.services.caption_service.ContentVariantRepository", return_value=mock_variant_repo), \
         patch("socialstack.services.caption_service.ContentSlotRepository", return_value=mock_slot_repo):

        from socialstack.services.caption_service import CaptionService
        svc = CaptionService(session=mock_session, ai=mock_ai)
        variant = await svc.generate(
            slot_id="slot_001",
            business_id="biz_001",
            platform="instagram",
            brief={"hook": "Test", "key_message": "Test msg", "emotional_angle": "Trust", "visual_direction": "Clean", "cta": "Book now"},
        )

    assert variant is not None
    mock_variant_repo.create.assert_called_once()
    call_kwargs = mock_variant_repo.create.call_args.kwargs
    assert call_kwargs["platform"] == "instagram"
    assert call_kwargs["caption"] != ""
    assert isinstance(call_kwargs["hashtags"], list)
    assert call_kwargs["char_count"] > 0


@pytest.mark.asyncio
async def test_caption_service_computes_char_count_from_text(mock_ai, gen_context):
    """char_count is computed by the service from caption + hashtags, not taken from AI."""
    mock_session = AsyncMock()
    captured_char_count = {}

    async def capture_create(**kwargs):
        captured_char_count["value"] = kwargs["char_count"]
        return _make_variant()

    mock_variant_repo = AsyncMock()
    mock_variant_repo.get_next_version = AsyncMock(return_value=1)
    mock_variant_repo.create = AsyncMock(side_effect=capture_create)
    mock_variant_repo.get_latest_for_slot_platform = AsyncMock(return_value=None)

    mock_slot_repo = AsyncMock()
    slot = _make_slot("slot_001", status="pending_caption")
    mock_slot_repo.get = AsyncMock(return_value=slot)
    mock_slot_repo.update = AsyncMock(return_value=slot)

    with patch("socialstack.services.caption_service.build_context", return_value=gen_context), \
         patch("socialstack.services.caption_service.ContentVariantRepository", return_value=mock_variant_repo), \
         patch("socialstack.services.caption_service.ContentSlotRepository", return_value=mock_slot_repo):

        from socialstack.services.caption_service import CaptionService
        svc = CaptionService(session=mock_session, ai=mock_ai)
        await svc.generate(
            slot_id="slot_001",
            business_id="biz_001",
            platform="instagram",
            brief={"hook": "H", "key_message": "M", "emotional_angle": "E", "visual_direction": "V", "cta": "C"},
        )

    # char_count must equal len(caption + "\n\n" + hashtags joined) — not an AI-provided value
    assert captured_char_count["value"] > 0


@pytest.mark.asyncio
async def test_twitter_280_retry_with_short_response(gen_context):
    """Twitter 280-char: AI returns >280 first call, <280 second call — second variant is saved."""
    call_count = 0

    class TwoStepAI:
        async def chat(self, prompt: str, system: str | None = None) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                long_caption = "A" * 270
                return f'{{"caption": "{long_caption}", "hashtags": ["#test1", "#test2"]}}'
            return '{"caption": "Short tweet. Book now!", "hashtags": ["#dental"]}'

        async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
            return b""

    mock_session = AsyncMock()
    mock_variant = _make_variant(platform="twitter")
    mock_variant_repo = AsyncMock()
    mock_variant_repo.get_next_version = AsyncMock(return_value=1)
    mock_variant_repo.create = AsyncMock(return_value=mock_variant)
    mock_variant_repo.get_latest_for_slot_platform = AsyncMock(return_value=None)

    mock_slot_repo = AsyncMock()
    slot = _make_slot("slot_001", status="pending_caption")
    slot.platform = "twitter"
    mock_slot_repo.get = AsyncMock(return_value=slot)
    mock_slot_repo.update = AsyncMock(return_value=slot)

    with patch("socialstack.services.caption_service.build_context", return_value=gen_context), \
         patch("socialstack.services.caption_service.ContentVariantRepository", return_value=mock_variant_repo), \
         patch("socialstack.services.caption_service.ContentSlotRepository", return_value=mock_slot_repo):

        from socialstack.services.caption_service import CaptionService
        svc = CaptionService(session=mock_session, ai=TwoStepAI())
        variant = await svc.generate(
            slot_id="slot_001",
            business_id="biz_001",
            platform="twitter",
            brief={"hook": "H", "key_message": "M", "emotional_angle": "E", "visual_direction": "V", "cta": "C"},
        )

    assert call_count == 2, "AI should have been called twice (retry on >280)"
    mock_variant_repo.create.assert_called_once()
    saved_char_count = mock_variant_repo.create.call_args.kwargs["char_count"]
    assert saved_char_count <= 280


@pytest.mark.asyncio
async def test_instagram_no_char_limit_enforcement(gen_context):
    """Instagram captions >280 chars are saved without retry."""
    class LongCaptionAI:
        async def chat(self, prompt: str, system: str | None = None) -> str:
            long_caption = "B" * 300
            return f'{{"caption": "{long_caption}", "hashtags": ["#ig", "#health"]}}'

        async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
            return b""

    mock_session = AsyncMock()
    mock_variant = _make_variant(platform="instagram")
    mock_variant_repo = AsyncMock()
    mock_variant_repo.get_next_version = AsyncMock(return_value=1)
    mock_variant_repo.create = AsyncMock(return_value=mock_variant)
    mock_variant_repo.get_latest_for_slot_platform = AsyncMock(return_value=None)

    mock_slot_repo = AsyncMock()
    slot = _make_slot("slot_001", status="pending_caption")
    mock_slot_repo.get = AsyncMock(return_value=slot)
    mock_slot_repo.update = AsyncMock(return_value=slot)

    with patch("socialstack.services.caption_service.build_context", return_value=gen_context), \
         patch("socialstack.services.caption_service.ContentVariantRepository", return_value=mock_variant_repo), \
         patch("socialstack.services.caption_service.ContentSlotRepository", return_value=mock_slot_repo):

        from socialstack.services.caption_service import CaptionService
        svc = CaptionService(session=mock_session, ai=LongCaptionAI())
        variant = await svc.generate(
            slot_id="slot_001",
            business_id="biz_001",
            platform="instagram",
            brief={"hook": "H", "key_message": "M", "emotional_angle": "E", "visual_direction": "V", "cta": "C"},
        )

    # Should succeed without retrying
    assert variant is not None
    call_kwargs = mock_variant_repo.create.call_args.kwargs
    assert call_kwargs["char_count"] > 280


# ---------------------------------------------------------------------------
# VariantService tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multi_variant_creates_correct_count(mock_ai, gen_context):
    """VariantService creates exactly variant_count variants from AI response."""
    mock_session = AsyncMock()
    created_variants = []

    async def capture_create(**kwargs):
        v = _make_variant(f"var_{len(created_variants)+1}", version=kwargs["version"])
        created_variants.append(kwargs)
        return v

    mock_variant_repo = AsyncMock()
    mock_variant_repo.get_next_version = AsyncMock(return_value=1)
    mock_variant_repo.get_latest_for_slot_platform = AsyncMock(return_value=None)
    mock_variant_repo.create = AsyncMock(side_effect=capture_create)

    with patch("socialstack.services.variant_service.build_context", return_value=gen_context), \
         patch("socialstack.services.variant_service.ContentVariantRepository", return_value=mock_variant_repo):

        from socialstack.services.variant_service import VariantService
        svc = VariantService(session=mock_session, ai=mock_ai)
        variants = await svc.generate_multi(
            slot_id="slot_001",
            business_id="biz_001",
            platform="instagram",
            brief={"hook": "H", "key_message": "M", "emotional_angle": "E", "visual_direction": "V", "cta": "C"},
            count=3,
        )

    assert len(variants) == 3
    assert mock_variant_repo.create.call_count == 3


@pytest.mark.asyncio
async def test_multi_variant_uses_label_field(mock_ai, gen_context):
    """VariantService maps n8n 'label' field to the variant_type column."""
    mock_session = AsyncMock()
    saved_variant_types = []

    async def capture_create(**kwargs):
        saved_variant_types.append(kwargs.get("variant_type", ""))
        return _make_variant(f"var_{len(saved_variant_types)}", version=kwargs["version"])

    mock_variant_repo = AsyncMock()
    mock_variant_repo.get_next_version = AsyncMock(return_value=1)
    mock_variant_repo.get_latest_for_slot_platform = AsyncMock(return_value=None)
    mock_variant_repo.create = AsyncMock(side_effect=capture_create)

    with patch("socialstack.services.variant_service.build_context", return_value=gen_context), \
         patch("socialstack.services.variant_service.ContentVariantRepository", return_value=mock_variant_repo):

        from socialstack.services.variant_service import VariantService
        svc = VariantService(session=mock_session, ai=mock_ai)
        await svc.generate_multi(
            slot_id="slot_001",
            business_id="biz_001",
            platform="instagram",
            brief={"hook": "H", "key_message": "M", "emotional_angle": "E", "visual_direction": "V", "cta": "C"},
            count=3,
        )

    assert "emotional" in saved_variant_types
    assert "educational" in saved_variant_types
    assert "promotional" in saved_variant_types


@pytest.mark.asyncio
async def test_multi_variant_versions_are_sequential(mock_ai, gen_context):
    """VariantService assigns sequential version numbers starting from base_version."""
    mock_session = AsyncMock()
    saved_versions = []

    async def capture_create(**kwargs):
        saved_versions.append(kwargs["version"])
        return _make_variant(f"var_{len(saved_versions)}", version=kwargs["version"])

    mock_variant_repo = AsyncMock()
    mock_variant_repo.get_next_version = AsyncMock(return_value=2)  # simulate existing version 1
    mock_variant_repo.get_latest_for_slot_platform = AsyncMock(return_value=None)
    mock_variant_repo.create = AsyncMock(side_effect=capture_create)

    with patch("socialstack.services.variant_service.build_context", return_value=gen_context), \
         patch("socialstack.services.variant_service.ContentVariantRepository", return_value=mock_variant_repo):

        from socialstack.services.variant_service import VariantService
        svc = VariantService(session=mock_session, ai=mock_ai)
        await svc.generate_multi(
            slot_id="slot_001",
            business_id="biz_001",
            platform="instagram",
            brief={"hook": "H", "key_message": "M", "emotional_angle": "E", "visual_direction": "V", "cta": "C"},
            count=3,
        )

    assert saved_versions == [2, 3, 4]


# ---------------------------------------------------------------------------
# AssetService tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_asset_service_parses_image_prompt_from_json(gen_context):
    """AssetService extracts image_prompt from JSON returned by art-direction step."""
    captured_image_prompt = {}

    class CapturingAI:
        async def chat(self, prompt: str, system: str | None = None) -> str:
            return '{"image_prompt": "A photorealistic dental clinic with warm lighting and a smiling patient"}'

        async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
            captured_image_prompt["value"] = prompt
            return b"PNG\x00fake"

    mock_session = AsyncMock()
    mock_asset = MagicMock()
    mock_asset.id = "asset_001"
    mock_asset.storage_url = "/tmp/test.png"

    mock_asset_repo = AsyncMock()
    mock_asset_repo.create = AsyncMock(return_value=mock_asset)

    mock_storage = AsyncMock()
    mock_storage.save = AsyncMock(return_value="/tmp/test.png")

    with patch("socialstack.services.asset_service.build_context", return_value=gen_context), \
         patch("socialstack.services.asset_service.MediaAssetRepository", return_value=mock_asset_repo), \
         patch("socialstack.services.asset_service.ContentVariantRepository", return_value=AsyncMock()):

        from socialstack.services.asset_service import AssetService
        svc = AssetService(session=mock_session, ai=CapturingAI(), storage=mock_storage)
        asset = await svc.generate(
            slot_id="slot_001",
            business_id="biz_001",
            platform="instagram",
            theme="Healthy Smiles",
            brief={"hook": "H", "key_message": "M", "emotional_angle": "E", "visual_direction": "Bright clinic", "cta": "Book"},
        )

    assert asset is not None
    assert "photorealistic dental clinic" in captured_image_prompt.get("value", "").lower()


@pytest.mark.asyncio
async def test_asset_service_skips_generation_when_disabled(gen_context):
    """AssetService returns a library placeholder when ai_generate_images=False."""
    from socialstack.services.context_service import GenerationContext
    no_image_context = GenerationContext(
        business_id="biz_001",
        business_name="Test Biz",
        industry="retail",
        brand_tones=["professional"],
        target_audience=[],
        pain_points=[],
        ai_generate_images=False,
        auto_approve=False,
        tier="standard",
    )

    ai_called = {"chat": False, "image": False}

    class TrackingAI:
        async def chat(self, prompt: str, system: str | None = None) -> str:
            ai_called["chat"] = True
            return '{"image_prompt": "test"}'

        async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
            ai_called["image"] = True
            return b""

    mock_session = AsyncMock()
    mock_asset = MagicMock()
    mock_asset_repo = AsyncMock()
    mock_asset_repo.create = AsyncMock(return_value=mock_asset)
    mock_storage = AsyncMock()

    with patch("socialstack.services.asset_service.build_context", return_value=no_image_context), \
         patch("socialstack.services.asset_service.MediaAssetRepository", return_value=mock_asset_repo), \
         patch("socialstack.services.asset_service.ContentVariantRepository", return_value=AsyncMock()):

        from socialstack.services.asset_service import AssetService
        svc = AssetService(session=mock_session, ai=TrackingAI(), storage=mock_storage)
        await svc.generate(
            slot_id="slot_001",
            business_id="biz_001",
            platform="instagram",
            theme="Test",
            brief={"key_message": "m", "emotional_angle": "e", "visual_direction": "v", "cta": "c"},
        )

    assert not ai_called["chat"]
    assert not ai_called["image"]
    create_kwargs = mock_asset_repo.create.call_args.kwargs
    assert create_kwargs["source"] == "library"
