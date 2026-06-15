import base64

from openai import AsyncOpenAI

from socialstack.utils.errors import AIError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider:
    def __init__(self, api_key: str, chat_model: str, image_model: str, max_retries: int = 3):
        self.chat_model = chat_model
        self.image_model = image_model
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

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        try:
            response = await self._client.images.generate(
                model=self.image_model,
                prompt=prompt,
                size=size,
                response_format="b64_json",
                n=1,
            )
            b64_data = response.data[0].b64_json
            if not b64_data:
                raise AIError("No image data in response", provider="openai")
            raw_bytes = base64.b64decode(b64_data)
            logger.info("openai_image_generated", model=self.image_model, size=size, bytes=len(raw_bytes))
            return raw_bytes
        except AIError:
            raise
        except Exception as e:
            raise AIError(str(e), provider="openai") from e
