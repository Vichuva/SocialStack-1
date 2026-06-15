from google import genai
from google.genai import types as gen_types

from socialstack.utils.errors import AIError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class GoogleImageProvider:
    def __init__(self, api_key: str, image_model: str = "imagen-3.0-generate-002", max_retries: int = 3):
        self.image_model = image_model
        self.max_retries = max_retries
        self._client = genai.Client(api_key=api_key)

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        try:
            response = self._client.models.generate_images(
                model=self.image_model,
                prompt=prompt,
                config=gen_types.GenerateImagesConfig(
                    number_of_images=1,
                    safety_filter_level=gen_types.SafetyFilterLevel.BLOCK_ONLY_HIGH,
                    person_generation=gen_types.PersonGeneration.ALLOW_ADULT,
                    output_mime_type="image/png",
                ),
            )
            image_bytes = response.generated_images[0].image.image_bytes
            logger.info("google_image_generated", model=self.image_model, bytes=len(image_bytes))
            return image_bytes
        except Exception as e:
            raise AIError(str(e), provider="google") from e
