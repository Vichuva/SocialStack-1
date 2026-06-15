from socialstack.utils.errors import AIError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class AnthropicProvider:
    """Claude provider — stub for future use. Wire in when needed."""

    def __init__(self, api_key: str, chat_model: str = "claude-sonnet-4-6"):
        self.chat_model = chat_model
        self._api_key = api_key

    async def chat(self, prompt: str, system: str | None = None) -> str:
        try:
            import anthropic
        except ImportError:
            raise AIError("anthropic package not installed", provider="anthropic")

        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        kwargs = {"model": self.chat_model, "max_tokens": 4096, "messages": [{"role": "user", "content": prompt}]}
        if system:
            kwargs["system"] = system
        try:
            response = await client.messages.create(**kwargs)
            text = response.content[0].text
            logger.info("anthropic_chat", model=self.chat_model, input_tokens=response.usage.input_tokens)
            return text
        except Exception as e:
            raise AIError(str(e), provider="anthropic") from e

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        raise AIError("Anthropic does not support image generation", provider="anthropic")
