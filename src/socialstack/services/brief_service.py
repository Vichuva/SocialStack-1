from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.ai.client import AIClient, parse_json_response
from socialstack.db.models.content import ContentBrief
from socialstack.repositories.content_repo import ContentBriefRepository, ContentSlotRepository
from socialstack.services.context_service import build_context
from socialstack.prompts.brief_prompt import build_brief_prompt
from socialstack.utils.errors import ValidationError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class BriefService:
    def __init__(self, session: AsyncSession, ai: AIClient):
        self.session = session
        self.ai = ai

    async def generate(self, slot_id: str, business_id: str, day: dict) -> ContentBrief:
        ctx = await build_context(self.session, business_id)

        prompt = build_brief_prompt(
            business_name=ctx.business_name,
            industry=ctx.industry,
            brand_tone=ctx.brand_tone,
            pain_points=ctx.pain_points,
            date=day.get("date", ""),
            theme=day.get("theme", ""),
            objective=day.get("objective", ""),
            post_idea=day.get("post_idea", ""),
        )

        raw = await self.ai.chat(prompt)
        data = parse_json_response(raw, provider="openai")

        if not isinstance(data, dict):
            raise ValidationError("AI returned invalid brief structure")

        repo = ContentBriefRepository(self.session)
        brief = await repo.create(
            slot_id=slot_id,
            business_id=business_id,
            hook=data.get("hook", ""),
            key_message=data.get("key_message", ""),
            emotional_angle=data.get("emotional_angle", ""),
            visual_direction=data.get("visual_direction", ""),
            cta=data.get("cta", ""),
        )

        # Advance slot status
        slot_repo = ContentSlotRepository(self.session)
        slot = await slot_repo.get(slot_id)
        if slot and slot.status in ("draft", "pending_brief"):
            await slot_repo.update(slot, status="pending_caption")

        logger.info("brief_generated", slot_id=slot_id, brief_id=brief.id)
        return brief
