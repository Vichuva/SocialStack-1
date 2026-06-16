import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.ai.client import AIClient
from socialstack.repositories.calendar_repo import CalendarRepository, CalendarDayRepository
from socialstack.repositories.content_repo import ContentSlotRepository
from socialstack.services.brief_service import BriefService
from socialstack.services.caption_service import CaptionService
from socialstack.services.asset_service import AssetService
from socialstack.services.context_service import build_context
from socialstack.utils.storage import get_storage
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class GenerationService:
    """WF-GENORCH: orchestrates full content generation for a calendar."""

    def __init__(self, session: AsyncSession, ai: AIClient):
        self.session = session
        self.ai = ai

    async def orchestrate(
        self,
        calendar_id: str,
        business_id: str,
        platforms: list[str],
        generate_images: bool = False,
        calendar_day_id: str | None = None,
    ) -> dict:
        cal_repo = CalendarRepository(self.session)
        day_repo = CalendarDayRepository(self.session)
        slot_repo = ContentSlotRepository(self.session)

        calendar = await cal_repo.get_or_raise(calendar_id)
        days = await day_repo.get_by_calendar(calendar_id)

        if calendar_day_id:
            days = [d for d in days if d.id == calendar_day_id]

        if not days:
            logger.warning("no_calendar_days_found", calendar_id=calendar_id)
            return {"calendar_id": calendar_id, "slots_generated": 0}

        brief_svc = BriefService(self.session, self.ai)
        caption_svc = CaptionService(self.session, self.ai)

        results = []

        for day in days:
            day_data = {
                "date": day.date,
                "theme": day.theme or "",
                "objective": day.objective or "awareness",
                "post_idea": day.post_idea or "",
            }

            # Create slots for each platform if they don't exist
            slot_ids: dict[str, str] = {}
            for platform in platforms:
                existing_slots = await slot_repo.get_by_calendar(calendar_id)
                slot_for_platform = next(
                    (s for s in existing_slots if s.calendar_day_id == day.id and s.platform == platform),
                    None
                )
                if not slot_for_platform:
                    slot = await slot_repo.create(
                        calendar_id=calendar_id,
                        calendar_day_id=day.id,
                        business_id=business_id,
                        platform=platform,
                        status="pending_brief",
                    )
                    slot_ids[platform] = slot.id
                else:
                    slot_ids[platform] = slot_for_platform.id

            # Generate brief ONCE per day (shared across platforms)
            # Use first platform's slot as the anchor slot for the brief
            anchor_slot_id = slot_ids[platforms[0]]
            brief = await brief_svc.generate(
                slot_id=anchor_slot_id,
                business_id=business_id,
                day=day_data,
            )
            brief_dict = {
                "hook": brief.hook,
                "key_message": brief.key_message,
                "emotional_angle": brief.emotional_angle,
                "visual_direction": brief.visual_direction,
                "cta": brief.cta,
            }

            # Generate captions in parallel (one per platform)
            caption_tasks = [
                caption_svc.generate(
                    slot_id=slot_ids[platform],
                    business_id=business_id,
                    platform=platform,
                    brief=brief_dict,
                )
                for platform in platforms
            ]
            variants = await asyncio.gather(*caption_tasks, return_exceptions=True)

            # Generate images if requested (with semaphore to limit concurrency)
            if generate_images:
                storage = get_storage()
                asset_svc = AssetService(self.session, self.ai, storage)
                sem = asyncio.Semaphore(5)

                async def _gen_asset(platform: str, variant_id: str | None):
                    async with sem:
                        return await asset_svc.generate(
                            slot_id=slot_ids[platform],
                            business_id=business_id,
                            platform=platform,
                            theme=day.theme or "",
                            brief=brief_dict,
                            variant_id=variant_id,
                        )

                asset_tasks = []
                for i, platform in enumerate(platforms):
                    v = variants[i]
                    vid = v.id if not isinstance(v, Exception) else None
                    asset_tasks.append(_gen_asset(platform, vid))
                await asyncio.gather(*asset_tasks, return_exceptions=True)

            # Mark slots pending_review
            for platform in platforms:
                slot = await slot_repo.get(slot_ids[platform])
                if slot and slot.status not in ("pending_review", "approved", "published"):
                    await slot_repo.update(slot, status="pending_review")

            results.append({
                "date": day.date,
                "theme": day.theme,
                "platforms": platforms,
                "slot_ids": slot_ids,
            })

        logger.info(
            "orchestration_complete",
            calendar_id=calendar_id,
            days=len(days),
            platforms=platforms,
            generate_images=generate_images,
        )
        return {
            "calendar_id": calendar_id,
            "days_processed": len(days),
            "platforms": platforms,
            "slots_generated": len(days) * len(platforms),
            "days": results,
        }
