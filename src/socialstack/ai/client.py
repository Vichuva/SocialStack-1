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


class CompositeAIClient:
    """Delegates chat → OpenAI, generate_image → Google."""

    def __init__(self, text_provider: "OpenAIProvider", image_provider: "GoogleImageProvider"):
        self._text = text_provider
        self._image = image_provider

    async def chat(self, prompt: str, system: str | None = None) -> str:
        return await self._text.chat(prompt, system=system)

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        return await self._image.generate_image(prompt, size=size)


def get_ai_client() -> AIClient:
    from socialstack.ai.google_provider import GoogleImageProvider
    from socialstack.ai.openai_provider import OpenAIProvider
    from socialstack.config import get_settings
    settings = get_settings()

    text_provider = OpenAIProvider(
        api_key=settings.openai_api_key,
        chat_model=settings.ai_chat_model,
        max_retries=settings.ai_max_retries,
    )
    image_provider = GoogleImageProvider(
        api_key=settings.google_api_key,
        image_model=settings.ai_image_model,
        max_retries=settings.ai_max_retries,
    )
    return CompositeAIClient(text_provider=text_provider, image_provider=image_provider)
