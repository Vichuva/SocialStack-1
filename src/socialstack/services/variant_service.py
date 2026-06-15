from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.ai.client import AIClient, parse_json_response
from socialstack.db.models.content import ContentVariant
from socialstack.platform_rules.rules import get_rules
from socialstack.prompts.multi_variant_prompt import build_multi_variant_prompt
from socialstack.repositories.content_repo import ContentVariantRepository
from socialstack.services.context_service import build_context
from socialstack.utils.errors import TwitterCharLimitError, ValidationError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class VariantService:
    def __init__(self, session: AsyncSession, ai: AIClient):
        self.session = session
        self.ai = ai

    async def generate_multi(
        self,
        slot_id: str,
        business_id: str,
        platform: str,
        brief: dict,
        count: int = 3,
    ) -> list[ContentVariant]:
        ctx = await build_context(self.session, business_id)
        rules = get_rules(platform)

        prompt = build_multi_variant_prompt(
            business_name=ctx.business_name,
            industry=ctx.industry,
            brand_tones=ctx.brand_tones,
            platform=platform,
            platform_rules=rules.system_rules,
            brief=brief,
            variant_count=count,
        )

        raw = await self.ai.chat(prompt)
        items = parse_json_response(raw, provider="openai")

        if not isinstance(items, list):
            raise ValidationError("AI returned invalid multi-variant structure")

        variant_repo = ContentVariantRepository(self.session)
        base_version = await variant_repo.get_next_version(slot_id, platform)
        saved: list[ContentVariant] = []

        for i, item in enumerate(items[:count]):
            caption = item.get("caption", "")
            hashtags = item.get("hashtags", [])
            if not isinstance(hashtags, list):
                hashtags = []

            full_text = caption
            if hashtags:
                full_text = f"{caption}\n\n{' '.join(hashtags)}"
            char_count = len(full_text)

            if platform == "twitter" and char_count > 280:
                logger.warning("multi_variant_twitter_overflow", index=i, char_count=char_count)
                continue

            variant = await variant_repo.create(
                slot_id=slot_id,
                business_id=business_id,
                platform=platform,
                caption=caption,
                hashtags=hashtags,
                char_count=char_count,
                version=base_version + i,
                variant_type=item.get("label", item.get("variant_type", "standard")),
            )
            saved.append(variant)

        logger.info("multi_variants_generated", slot_id=slot_id, platform=platform, count=len(saved))
        return saved
