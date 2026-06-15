import json
import re
from typing import Protocol, runtime_checkable

from socialstack.utils.errors import AIParseError


@runtime_checkable
class AIClient(Protocol):
    async def chat(self, prompt: str, system: str | None = None) -> str:
        """Send a prompt and return the text response."""
        ...

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        """Generate an image from prompt; return raw PNG/JPEG bytes."""
        ...


def parse_json_response(raw: str, provider: str = "unknown") -> dict | list:
    """Strip markdown fences and parse JSON from an AI text response."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise AIParseError(raw, provider) from e


def get_ai_client() -> AIClient:
    from socialstack.config import get_settings
    settings = get_settings()

    if settings.ai_provider == "openai":
        from socialstack.ai.openai_provider import OpenAIProvider
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            chat_model=settings.ai_chat_model,
            image_model=settings.ai_image_model,
            max_retries=settings.ai_max_retries,
        )
    elif settings.ai_provider == "anthropic":
        from socialstack.ai.anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            chat_model=settings.ai_chat_model,
        )
    else:
        raise ValueError(f"Unknown AI provider: {settings.ai_provider}")
