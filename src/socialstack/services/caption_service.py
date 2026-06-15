from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.ai.client import AIClient, parse_json_response
from socialstack.db.models.content import ContentVariant
from socialstack.platform_rules.rules import get_rules
from socialstack.prompts.caption_prompt import build_caption_prompt
from socialstack.repositories.content_repo import ContentSlotRepository, ContentVariantRepository
from socialstack.services.context_service import build_context
from socialstack.utils.errors import TwitterCharLimitError, ValidationError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class CaptionService:
    def __init__(self, session: AsyncSession, ai: AIClient):
        self.session = session
        self.ai = ai

    async def generate(
        self,
        slot_id: str,
        business_id: str,
        platform: str,
        brief: dict,
        retry_shorten: bool = False,
    ) -> ContentVariant:
        ctx = await build_context(self.session, business_id)
        rules = get_rules(platform)

        system_rules = rules.system_rules
        if retry_shorten:
            system_rules += (
                "\n\nCRITICAL CONSTRAINT: The previous attempt exceeded the 280 char limit. "
                "You MUST make the caption shorter. Aim for 240 chars total including hashtags."
            )

        prompt = build_caption_prompt(
            business_name=ctx.business_name,
            industry=ctx.industry,
            brand_tone=ctx.brand_tone,
            platform=platform,
            platform_rules=system_rules,
            brief=brief,
        )

        raw = await self.ai.chat(prompt)
        data = parse_json_response(raw, provider="openai")

        if not isinstance(data, dict):
            raise ValidationError("AI returned invalid caption structure")

        caption = data.get("caption", "")
        hashtags = data.get("hashtags", [])
        if not isinstance(hashtags, list):
            hashtags = []

        # Compute real char count
        full_text = caption
        if hashtags:
            full_text = f"{caption}\n\n{' '.join(hashtags)}"
        char_count = len(full_text)

        # Twitter 280-char guard — stage 1
        if platform == "twitter" and char_count > 280:
            if not retry_shorten:
                logger.warning("twitter_char_limit_exceeded", char_count=char_count, retrying=True)
                return await self.generate(
                    slot_id=slot_id,
                    business_id=business_id,
                    platform=platform,
                    brief=brief,
                    retry_shorten=True,
                )
            raise TwitterCharLimitError(char_count)

        # Get next version number
        variant_repo = ContentVariantRepository(self.session)
        version = await variant_repo.get_next_version(slot_id, platform)

        variant = await variant_repo.create(
            slot_id=slot_id,
            business_id=business_id,
            platform=platform,
            caption=caption,
            hashtags=hashtags,
            char_count=char_count,
            version=version,
            variant_type="standard",
        )

        # Advance slot to pending_review
        slot_repo = ContentSlotRepository(self.session)
        slot = await slot_repo.get(slot_id)
        if slot and slot.status in ("pending_caption",):
            await slot_repo.update(slot, status="pending_review")

        logger.info("caption_generated", slot_id=slot_id, platform=platform, char_count=char_count, version=version)
        return variant
