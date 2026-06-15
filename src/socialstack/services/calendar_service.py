import calendar as cal_module
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.ai.client import AIClient, parse_json_response
from socialstack.db.models.content import ContentSlot
from socialstack.db.models.social import SocialPlatformConnection
from socialstack.repositories.calendar_repo import CalendarDayRepository, CalendarRepository
from socialstack.repositories.schedule_repo import SlotScheduleTemplateRepository
from socialstack.services.context_service import build_context
from socialstack.prompts.calendar_prompt import build_calendar_prompt
from socialstack.utils.errors import NotFoundError, ValidationError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)

VALID_OBJECTIVES = {"awareness", "education", "promotion", "trust", "engagement"}


class CalendarService:
    def __init__(self, session: AsyncSession, ai: AIClient):
        self.session = session
        self.ai = ai

    async def generate_themes(self, calendar_id: str) -> dict:
        cal_repo = CalendarRepository(self.session)
        day_repo = CalendarDayRepository(self.session)

        calendar = await cal_repo.get_or_raise(calendar_id)
        ctx = await build_context(self.session, calendar.business_id)

        prompt = build_calendar_prompt(
            business_name=ctx.business_name,
            industry=ctx.industry,
            brand_tones=ctx.brand_tones,
            pain_points=ctx.pain_points,
            offerings=[],
            month=calendar.month,
            year=calendar.year,
        )

        raw = await self.ai.chat(prompt)
        themes = parse_json_response(raw, provider="openai")

        if not isinstance(themes, list) or not themes:
            raise ValidationError("AI returned empty or invalid themes array")

        days_in_month = cal_module.monthrange(calendar.year, calendar.month)[1]

        saved_days = []
        for item in themes:
            day_num = int(item.get("day", 0))
            if not (1 <= day_num <= days_in_month):
                continue

            date_str = f"{calendar.year:04d}-{calendar.month:02d}-{day_num:02d}"
            objective = item.get("objective", "awareness")
            if objective not in VALID_OBJECTIVES:
                objective = "awareness"

            existing = await day_repo.get_by_date(calendar_id, date_str)
            if existing:
                day = await day_repo.update(
                    existing,
                    theme=item.get("theme"),
                    objective=objective,
                    post_idea=item.get("post_idea"),
                )
                saved_days.append(day)
            else:
                day = await day_repo.create(
                    calendar_id=calendar_id,
                    date=date_str,
                    day_number=day_num,
                    theme=item.get("theme"),
                    objective=objective,
                    post_idea=item.get("post_idea"),
                )
                saved_days.append(day)

        slots_created = await self._materialize_slots(
            calendar=calendar,
            calendar_days=saved_days,
            business_id=calendar.business_id,
        )

        await cal_repo.update(calendar, status="themes_generated")

        logger.info(
            "calendar_themes_generated",
            calendar_id=calendar_id,
            days_saved=len(saved_days),
            slots_created=slots_created,
        )
        return {
            "calendar_id": calendar_id,
            "days_generated": len(saved_days),
            "slots_created": slots_created,
        }

    async def _materialize_slots(self, calendar, calendar_days: list, business_id: str) -> int:
        """Create ContentSlots from SlotScheduleTemplates for each calendar day."""
        template_repo = SlotScheduleTemplateRepository(self.session)
        templates = await template_repo.list_for_business(business_id, active_only=True)
        if not templates:
            return 0

        stmt = select(SocialPlatformConnection).where(
            and_(
                SocialPlatformConnection.business_id == business_id,
                SocialPlatformConnection.is_active.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        connections = result.scalars().all()
        if not connections:
            return 0

        template_by_dow = {}
        for t in templates:
            template_by_dow.setdefault(t.day_of_week, []).append(t)

        created = 0
        for day in calendar_days:
            try:
                date_obj = datetime.strptime(day.date, "%Y-%m-%d")
            except ValueError:
                continue
            dow = date_obj.weekday()  # 0=Monday

            matched = template_by_dow.get(dow, [])
            for template in matched:
                h, m = template.post_time.split(":")
                scheduled_at = date_obj.replace(
                    hour=int(h), minute=int(m), second=0, microsecond=0,
                    tzinfo=timezone.utc,
                )
                for conn in connections:
                    existing = await self.session.execute(
                        select(ContentSlot).where(
                            and_(
                                ContentSlot.calendar_day_id == day.id,
                                ContentSlot.platform == conn.platform,
                                ContentSlot.scheduled_at == scheduled_at,
                            )
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    slot = ContentSlot(
                        calendar_id=calendar.id,
                        calendar_day_id=day.id,
                        business_id=business_id,
                        platform=conn.platform,
                        content_type=template.content_type,
                        scheduled_at=scheduled_at,
                        status="draft",
                    )
                    self.session.add(slot)
                    created += 1

        if created:
            await self.session.flush()

        return created
