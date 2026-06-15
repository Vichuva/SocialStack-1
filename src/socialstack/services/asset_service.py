from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.ai.client import AIClient, parse_json_response
from socialstack.db.models.media import MediaAsset
from socialstack.platform_rules.rules import get_rules
from socialstack.prompts.image_prompt import build_image_art_direction_prompt
from socialstack.repositories.media_repo import MediaAssetRepository
from socialstack.repositories.content_repo import ContentVariantRepository
from socialstack.services.context_service import build_context
from socialstack.utils.storage import StorageBackend
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class AssetService:
    def __init__(self, session: AsyncSession, ai: AIClient, storage: StorageBackend):
        self.session = session
        self.ai = ai
        self.storage = storage

    async def generate(
        self,
        slot_id: str,
        business_id: str,
        platform: str,
        theme: str,
        brief: dict,
        variant_id: str | None = None,
    ) -> MediaAsset:
        ctx = await build_context(self.session, business_id)

        if not ctx.ai_generate_images:
            logger.info("asset_generation_skipped", reason="ai_generate_images=False", slot_id=slot_id)
            # Return a placeholder — real implementation would pick from media library
            repo = MediaAssetRepository(self.session)
            return await repo.create(
                business_id=business_id,
                variant_id=variant_id,
                storage_url="",
                asset_type="image",
                mime_type="image/png",
                source="library",
                platform=platform,
            )

        rules = get_rules(platform)

        # Step 1: Generate art-direction prompt via LLM (returns JSON {"image_prompt": "..."})
        art_prompt = build_image_art_direction_prompt(
            business_name=ctx.business_name,
            industry=ctx.industry,
            brand_tone=ctx.brand_tone,
            platform=platform,
            theme=theme,
            brief=brief,
        )
        raw = await self.ai.chat(art_prompt)
        parsed = parse_json_response(raw, provider="openai")
        image_prompt = parsed.get("image_prompt", "") if isinstance(parsed, dict) else raw.strip()

        # Step 2: Generate image bytes
        image_bytes = await self.ai.generate_image(image_prompt, size=rules.image_size)

        # Step 3: Store
        filename = f"{slot_id}_{platform}.png"
        url = await self.storage.save(image_bytes, filename, "image/png")

        # Step 4: Persist media asset record
        asset_repo = MediaAssetRepository(self.session)
        asset = await asset_repo.create(
            business_id=business_id,
            variant_id=variant_id,
            storage_url=url,
            asset_type="image",
            mime_type="image/png",
            file_size_bytes=len(image_bytes),
            source="ai_generated",
            ai_prompt=image_prompt,
            platform=platform,
        )

        logger.info("asset_generated", slot_id=slot_id, platform=platform, url=url, size=len(image_bytes))
        return asset
