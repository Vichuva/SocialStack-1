import google.generativeai as genai
from google.generativeai import types as gen_types

from socialstack.utils.errors import AIError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class GoogleImageProvider:
    def __init__(self, api_key: str, image_model: str = "nano-banana-pro", max_retries: int = 3):
        self.image_model = image_model
        self.max_retries = max_retries
        genai.configure(api_key=api_key)
        self._client = genai.ImageGenerationModel(image_model)

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        try:
            response = self._client.generate_images(
                prompt=prompt,
                number_of_images=1,
                safety_filter_level=gen_types.SafetyFilterLevel.BLOCK_ONLY_HIGH,
                person_generation=gen_types.PersonGeneration.ALLOW_ADULT,
            )
            image = response.images[0]
            raw_bytes = image._pil_image.tobytes() if hasattr(image, "_pil_image") else bytes(image)
            logger.info("google_image_generated", model=self.image_model, size=size, bytes=len(raw_bytes))
            return raw_bytes
        except Exception as e:
            raise AIError(str(e), provider="google") from e
