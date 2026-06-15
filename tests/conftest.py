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
    """Deterministic AI responses for testing."""

    async def chat(self, prompt: str, system: str | None = None) -> str:
        if "JSON array" in prompt and "theme" in prompt:
            return '[{"day": 1, "theme": "Test Theme", "objective": "awareness", "post_idea": "Test idea"}]'
        if "creative brief" in prompt.lower() or "hook" in prompt.lower():
            return '{"hook": "Test hook", "key_message": "Test message", "emotional_angle": "Test angle", "visual_direction": "Test visual", "cta": "Test CTA"}'
        if "caption" in prompt.lower():
            return '{"caption": "Test caption text", "hashtags": ["#test", "#social"], "char_count": 30}'
        if "art director" in prompt.lower() or "image" in prompt.lower():
            return "A vibrant professional image showing business growth"
        if "feedback" in prompt.lower() and "adjusted_hook" in prompt:
            return '{"adjusted_hook": "New hook", "adjusted_key_message": "New message", "adjusted_emotional_angle": "educational", "adjusted_visual_direction": "Clean", "adjusted_cta": "Learn more", "tone_shift": "more educational", "summary": "Made it more educational"}'
        return '{"result": "mock response"}'

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        return b"PNG\x00fake_image_bytes"


@pytest.fixture
def mock_ai():
    return MockAIClient()
