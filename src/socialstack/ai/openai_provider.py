from openai import AsyncOpenAI

from socialstack.utils.errors import AIError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider:
    """Handles text generation only. Image generation is handled by GoogleImageProvider."""

    def __init__(self, api_key: str, chat_model: str, max_retries: int = 3):
        self.chat_model = chat_model
        self._client = AsyncOpenAI(api_key=api_key, max_retries=max_retries)

    async def chat(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
            )
            text = response.choices[0].message.content or ""
            logger.info(
                "openai_chat",
                model=self.chat_model,
                prompt_tokens=response.usage.prompt_tokens if response.usage else None,
                completion_tokens=response.usage.completion_tokens if response.usage else None,
            )
            return text
        except Exception as e:
            raise AIError(str(e), provider="openai") from e
