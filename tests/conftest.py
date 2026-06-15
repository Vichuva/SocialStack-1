import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://socialstack:password@localhost:5432/socialstack_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/9")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/9")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/9")
os.environ.setdefault("AI_PROVIDER", "openai")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("LOCAL_STORAGE_PATH", "/tmp/socialstack_test_media")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "Yj-QeD7W_kWnWQVBxn6VMh3pCy7HlU7TMn2Eq_Rl0So=")
os.environ.setdefault("API_SECRET_KEY", "test-key")
os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture(scope="session")
def app():
    from socialstack.app import create_app
    return create_app()


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class MockAIClient:
    """Deterministic AI client for testing. Responses keyed to prompt keywords."""

    async def chat(self, prompt: str, system: str | None = None) -> str:
        p = prompt.lower()

        # Calendar themes — "json array" + "objective" in prompt
        if "json array" in p and "objective" in p and "day" in p:
            return (
                '[{"day": 1, "theme": "Healthy Smiles", "objective": "awareness", "post_idea": "Share tips for daily dental care"},'
                ' {"day": 2, "theme": "Pain-Free Visits", "objective": "trust", "post_idea": "Highlight our gentle treatment approach"}]'
            )

        # Multi-variant — "a/b test" or "label=emotional" in prompt (check before generic caption)
        if "a/b test" in p or "label=emotional" in p:
            return (
                '[{"label": "emotional", "approach": "Storytelling angle", "hook": "Your smile deserves the best", '
                '"caption": "Every visit, we put your comfort first. Experience dentistry that feels different.", '
                '"hashtags": ["#DentalCare", "#ComfortFirst"], "cta": "Book your appointment"},'
                '{"label": "educational", "approach": "Educational angle", "hook": "Did you know?", '
                '"caption": "Regular check-ups prevent 90% of dental issues before they become costly problems.", '
                '"hashtags": ["#DentalTips", "#PreventiveCare"], "cta": "Schedule a check-up"},'
                '{"label": "promotional", "approach": "Promotional angle", "hook": "Limited offer", '
                '"caption": "New patient special: complete check-up and clean for a fraction of the regular price.", '
                '"hashtags": ["#NewPatient", "#DentalOffer"], "cta": "Claim your spot"}]'
            )

        # Image art direction — "image-prompt engineer" or "viral-worthy" in prompt
        if "image-prompt engineer" in p or "viral-worthy" in p:
            return (
                '{"image_prompt": "A warm, inviting dental clinic reception with soft natural lighting, '
                'a smiling dental professional in white coat, shallow depth of field, editorial photography style, '
                'color palette of warm whites and sage green, no text or logos"}'
            )

        # Brief — "senior creative director" or "creative brief for one"
        if "senior creative director" in p or "creative brief for one" in p:
            return (
                '{"hook": "Your healthy smile starts with one simple visit", '
                '"key_message": "Regular dental check-ups are the foundation of long-term oral health", '
                '"emotional_angle": "warmth and reassurance — ease the fear, build the trust", '
                '"visual_direction": "A smiling patient in a bright modern dental chair, natural light, clinician in background", '
                '"cta": "Book your next appointment today"}'
            )

        # Caption — "write one caption" or "expert social media copywriter" + "caption"
        if "write one caption" in p or ("expert social media copywriter" in p and "approved creative brief" in p):
            return (
                '{"caption": "Your smile is our priority. Every visit, our team makes sure you leave feeling confident and cared for.", '
                '"hashtags": ["#DentalCare", "#HealthySmile", "#OralHealth"]}'
            )

        # Regen analysis — "adjusted_hook" in prompt
        if "adjusted_hook" in p:
            return (
                '{"adjusted_hook": "Did you know painless dentistry is now a reality?", '
                '"adjusted_key_message": "Modern techniques make dental visits comfortable and quick", '
                '"adjusted_emotional_angle": "educational curiosity — inform and reassure", '
                '"adjusted_visual_direction": "Clean minimal photo of modern dental equipment, no patient visible", '
                '"adjusted_cta": "Learn more about our gentle approach", '
                '"tone_shift": "more educational", '
                '"summary": "Shifted from emotional appeal to educational reassurance based on feedback requesting more facts"}'
            )

        return '{"result": "mock response"}'

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        return b"PNG\x00fake_image_bytes"


@pytest.fixture
def mock_ai():
    return MockAIClient()
