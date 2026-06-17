from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.ai.client import AIClient, parse_json_response
from socialstack.db.models.content import ContentVariant
from socialstack.prompts.regen_prompt import build_regen_analysis_prompt
from socialstack.repositories.content_repo import ContentBriefRepository, ContentSlotRepository, ContentVariantRepository
from socialstack.services.caption_service import CaptionService
from socialstack.utils.errors import ValidationError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class RegenerationService:
    """WF-REGEN: analyzes feedback, adjusts brief, regenerates caption."""

    def __init__(self, session: AsyncSession, ai: AIClient):
        self.session = session
        self.ai = ai

    async def regenerate(
        self,
        slot_id: str,
        business_id: str,
        platform: str,
        feedback: str,
        original_brief: dict,
    ) -> ContentVariant:
        # Step 1: Analyze feedback and adjust the brief
        analysis_prompt = build_regen_analysis_prompt(feedback, original_brief)
        raw = await self.ai.chat(analysis_prompt)
        analysis = parse_json_response(raw, provider="openai")

        if not isinstance(analysis, dict):
            raise ValidationError("AI returned invalid regen analysis structure")

        enhanced_brief = {
            "hook": analysis.get("adjusted_hook") or original_brief.get("hook", ""),
            "key_message": analysis.get("adjusted_key_message") or original_brief.get("key_message", ""),
            "emotional_angle": analysis.get("adjusted_emotional_angle") or original_brief.get("emotional_angle", ""),
            "visual_direction": analysis.get("adjusted_visual_direction") or original_brief.get("visual_direction", ""),
            "cta": analysis.get("adjusted_cta") or original_brief.get("cta", ""),
        }
        tone_shift = analysis.get("tone_shift", "")
        summary = analysis.get("summary", "")

        logger.info("regen_analysis_complete", slot_id=slot_id, tone_shift=tone_shift, summary=summary)

        # Step 2: Supersede the current variant for this slot+platform (version history)
        variant_repo = ContentVariantRepository(self.session)
        old_variant = await variant_repo.get_current_for_slot_platform(slot_id, platform)
        old_regen_count = 0
        if old_variant:
            old_regen_count = old_variant.regeneration_count
            await variant_repo.set_superseded(old_variant.id)

        # Step 3: Generate new caption with enhanced brief
        caption_svc = CaptionService(self.session, self.ai)
        variant = await caption_svc.generate(
            slot_id=slot_id,
            business_id=business_id,
            platform=platform,
            brief=enhanced_brief,
        )
        # Increment regeneration_count on the new variant
        await variant_repo.update(variant, regeneration_count=old_regen_count + 1)

        # Step 3: Slot back to pending_review
        slot_repo = ContentSlotRepository(self.session)
        slot = await slot_repo.get(slot_id)
        if slot:
            await slot_repo.update(slot, status="pending_review")

        logger.info(
            "regen_complete",
            slot_id=slot_id,
            platform=platform,
            new_variant_id=variant.id,
            version=variant.version,
            tone_shift=tone_shift,
        )
        return variant
