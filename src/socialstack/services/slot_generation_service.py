"""
Slot-centric AI generation service.

Operates directly on ContentSlot rows (no CalendarDay dependency).
Used by the SuperOne-compatible /api/v1/content/* endpoints.
"""
import calendar as cal_module
import json
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.ai.client import get_ai_client, parse_json_response
from socialstack.db.models.content import ContentSlot, ContentVariant
from socialstack.db.models.social import SocialPlatformConnection
from socialstack.platform_rules.rules import get_rules
from socialstack.repositories.content_repo import ContentSlotRepository, ContentVariantRepository
from socialstack.services.context_service import build_context
from socialstack.utils.errors import ValidationError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)

PLATFORM_CHAR_LIMITS = {
    "twitter": 280,
    "facebook": 2000,
    "instagram": 2200,
    "tiktok": 2200,
    "linkedin": 3000,
    "threads": 500,
    "youtube_shorts": 100,
}

VALID_OBJECTIVES = {"awareness", "engagement", "conversion", "retention", "pain_point"}


class SlotGenerationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.ai = get_ai_client()

    async def _get_empty_slots_for_month(
        self, business_id: str, month: int, year: int
    ) -> list[ContentSlot]:
        stmt = select(ContentSlot).where(
            and_(
                ContentSlot.business_id == business_id,
                ContentSlot.scheduled_at != None,  # noqa: E711
            )
        )
        result = await self.session.execute(stmt)
        all_slots = result.scalars().all()
        return [
            s for s in all_slots
            if s.scheduled_at
            and s.scheduled_at.month == month
            and s.scheduled_at.year == year
            and s.status == "empty"
        ]

    async def _get_active_platforms(self, business_id: str) -> list[str]:
        stmt = select(SocialPlatformConnection).where(
            and_(
                SocialPlatformConnection.business_id == business_id,
                SocialPlatformConnection.is_active.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        conns = result.scalars().all()
        return [c.platform for c in conns] if conns else ["instagram"]

    # ── generate_themes ───────────────────────────────────────────────────────

    async def generate_themes(self, business_id: str, month: int, year: int) -> dict:
        empty_slots = await self._get_empty_slots_for_month(business_id, month, year)
        if not empty_slots:
            raise ValidationError("no_empty_slots: No empty slots found for this month")

        ctx = await build_context(self.session, business_id)
        month_name = cal_module.month_name[month]

        slot_dates = [
            s.scheduled_at.strftime("%Y-%m-%d") for s in empty_slots if s.scheduled_at
        ]
        slot_list = "\n".join(f"- {d}" for d in slot_dates)

        prompt = f"""You are a social media content strategist for {ctx.business_name} ({ctx.industry}).

Brand tone: {ctx.brand_tone_str}
Pain points we address: {", ".join(ctx.pain_points) if ctx.pain_points else "general business challenges"}

Generate a unique, compelling content theme for each of the {len(empty_slots)} scheduled posts in {month_name} {year}.

Scheduled dates:
{slot_list}

Return a JSON array. Each element must have exactly these fields:
- "date": the exact date string from the list above (YYYY-MM-DD)
- "theme": a short, catchy theme title (max 80 chars)
- "objective": one of: awareness, engagement, conversion, retention, pain_point
- "problem": one sentence describing the problem this post solves (max 150 chars)
- "solution": one sentence describing what the post will show (max 150 chars)
- "impact": one sentence on the expected audience impact (max 150 chars)

Return ONLY the JSON array, no markdown, no explanation."""

        raw = await self.ai.chat(prompt)
        themes = parse_json_response(raw, provider="openai")

        if not isinstance(themes, list):
            raise ValidationError("ai_unavailable: AI returned invalid response")

        # Build date → slot map
        date_to_slot = {}
        for s in empty_slots:
            if s.scheduled_at:
                date_to_slot[s.scheduled_at.strftime("%Y-%m-%d")] = s

        slot_repo = ContentSlotRepository(self.session)
        updated_slots = []

        for item in themes:
            date_str = item.get("date", "")
            slot = date_to_slot.get(date_str)
            if not slot:
                continue

            objective = item.get("objective", "awareness")
            if objective not in VALID_OBJECTIVES:
                objective = "awareness"

            slot = await slot_repo.update(
                slot,
                theme=item.get("theme"),
                objective=objective,
                problem=item.get("problem"),
                solution=item.get("solution"),
                impact=item.get("impact"),
                status="pending_review",
                generation_attempt=slot.generation_attempt + 1,
            )
            updated_slots.append(slot)

        logger.info("slot_themes_generated", business_id=business_id, month=month, year=year, count=len(updated_slots))
        return {
            "generated": len(updated_slots),
            "slots": [
                {
                    "id": s.id,
                    "date": s.scheduled_at.strftime("%Y-%m-%d") if s.scheduled_at else None,
                    "theme": s.theme,
                    "objective": s.objective,
                    "problem": s.problem,
                    "status": s.status,
                }
                for s in updated_slots
            ],
        }

    # ── generate_variants (batch for whole month) ─────────────────────────────

    async def generate_variants(self, business_id: str, month: int, year: int) -> dict:
        # Find slots that have a theme but no current variants
        stmt = select(ContentSlot).where(
            and_(
                ContentSlot.business_id == business_id,
                ContentSlot.scheduled_at != None,  # noqa: E711
                ContentSlot.theme != None,  # noqa: E711
            )
        )
        result = await self.session.execute(stmt)
        all_slots = result.scalars().all()

        month_slots = [
            s for s in all_slots
            if s.scheduled_at and s.scheduled_at.month == month and s.scheduled_at.year == year
        ]

        # Filter to slots without current variants
        variant_repo = ContentVariantRepository(self.session)
        slots_without_variants = []
        for slot in month_slots:
            existing = await variant_repo.get_current_for_slot(slot.id)
            if not existing:
                slots_without_variants.append(slot)

        if not slots_without_variants:
            return {"slots_processed": 0, "variants_created": 0, "failed_slots": []}

        platforms = await self._get_active_platforms(business_id)
        ctx = await build_context(self.session, business_id)

        slots_processed = 0
        variants_created = 0
        failed_slots = []

        for slot in slots_without_variants:
            try:
                for platform in platforms:
                    v = await self._generate_one_variant(slot, platform, ctx, feedback=None)
                    if v:
                        variants_created += 1
                slots_processed += 1
            except Exception as exc:
                logger.error("variant_generation_failed", slot_id=slot.id, error=str(exc))
                failed_slots.append({"slot_id": slot.id, "error": str(exc)})

        logger.info(
            "batch_variants_generated",
            business_id=business_id,
            slots_processed=slots_processed,
            variants_created=variants_created,
        )
        return {
            "slots_processed": slots_processed,
            "variants_created": variants_created,
            "failed_slots": failed_slots,
        }

    # ── generate_variants_for_slot (per-slot regen) ───────────────────────────

    async def generate_variants_for_slot(
        self,
        slot: ContentSlot,
        platforms: list[str] | None,
        feedback: str | None,
    ) -> dict:
        active_platforms = await self._get_active_platforms(slot.business_id)
        target_platforms = platforms if platforms else active_platforms
        ctx = await build_context(self.session, slot.business_id)
        variant_repo = ContentVariantRepository(self.session)

        regenerated_platforms = []
        new_variants = []

        for platform in target_platforms:
            # Supersede existing current variant
            current = await variant_repo.get_current_for_slot_platform(slot.id, platform)
            if current:
                await variant_repo.update(current, is_current=False, is_active=False)

            v = await self._generate_one_variant(slot, platform, ctx, feedback=feedback)
            if v:
                regenerated_platforms.append(platform)
                new_variants.append({
                    "id": v.id,
                    "platform": v.platform,
                    "content": v.content or v.caption,
                    "version": v.version,
                    "is_current": v.is_current,
                    "review_status": v.review_status,
                })

        # Reset slot status
        slot_repo = ContentSlotRepository(self.session)
        await slot_repo.update(slot, status="pending_review")

        return {"regenerated": regenerated_platforms, "variants": new_variants}

    # ── internal: generate one variant via AI ────────────────────────────────

    async def _generate_one_variant(self, slot: ContentSlot, platform: str, ctx, feedback: str | None) -> ContentVariant | None:
        char_limit = PLATFORM_CHAR_LIMITS.get(platform, 2200)
        rules = get_rules(platform)

        feedback_line = f"\nUser feedback to address: {feedback}" if feedback else ""

        prompt = f"""Write a {platform} post for {ctx.business_name} ({ctx.industry}).

Brand tone: {ctx.brand_tone_str}
Pain points: {", ".join(ctx.pain_points) if ctx.pain_points else "general business challenges"}

Post theme: {slot.theme or "General brand content"}
Objective: {slot.objective or "awareness"}
Key message: {slot.problem or ""}
Approach: {slot.solution or ""}
{feedback_line}

Platform: {platform}
Character limit: {char_limit} characters
Platform rules: {rules.system_rules}

Return a JSON object with exactly:
- "caption": the post text (no hashtags, within char limit)
- "hashtags": array of 3–7 relevant hashtags (strings starting with #)

Return ONLY the JSON object, no markdown."""

        raw = await self.ai.chat(prompt)
        data = parse_json_response(raw, provider="openai")
        if not isinstance(data, dict):
            return None

        caption = data.get("caption", "")
        hashtags = data.get("hashtags", [])
        if not isinstance(hashtags, list):
            hashtags = []

        full_text = caption
        if hashtags:
            full_text = f"{caption}\n\n{' '.join(hashtags)}"
        char_count = len(full_text)

        if platform == "twitter" and char_count > 280:
            caption = caption[:250] + "..."
            char_count = len(caption)
            hashtags = hashtags[:2]

        variant_repo = ContentVariantRepository(self.session)
        next_version = await variant_repo.get_next_version(slot.id, platform)

        existing_count = 0
        current = await variant_repo.get_latest_for_slot_platform(slot.id, platform)
        if current:
            existing_count = current.regeneration_count

        return await variant_repo.create(
            slot_id=slot.id,
            business_id=slot.business_id,
            platform=platform,
            caption=caption,
            content=full_text,
            hashtags=hashtags,
            char_count=char_count,
            version=next_version,
            review_status="pending",
            is_current=True,
            is_active=True,
            regeneration_count=existing_count + (1 if next_version > 1 else 0),
            generation_metadata={"hashtags": hashtags, "model": "gpt-4o-mini", "feedback": feedback},
        )
