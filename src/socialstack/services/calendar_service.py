import calendar as cal_module
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.ai.client import AIClient, parse_json_response
from socialstack.db.models.content import ContentSlot
from socialstack.db.models.social import SocialPlatformConnection
from socialstack.repositories.business_repo import BusinessPreferencesRepository, BusinessRepository
from socialstack.repositories.calendar_repo import CalendarDayRepository, CalendarRepository
from socialstack.repositories.content_repo import ContentSlotRepository
from socialstack.repositories.schedule_repo import SlotScheduleTemplateRepository
from socialstack.services.context_service import build_context
from socialstack.prompts.calendar_prompt import build_calendar_prompt
from socialstack.utils.errors import NotFoundError, ValidationError
from socialstack.utils.logging import get_logger

WEEKDAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

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

    async def sync_slots_from_schedule(
        self, business_id: str, month: int, year: int
    ) -> dict:
        """
        Create empty ContentSlots based on posting_schedule JSONB in preferences.
        Never touches slots with status 'approved' or 'published'.
        Returns counts of created vs skipped.
        """
        prefs_repo = BusinessPreferencesRepository(self.session)
        biz_repo = BusinessRepository(self.session)
        slot_repo = ContentSlotRepository(self.session)

        business = await biz_repo.get_or_raise(business_id)
        prefs = await prefs_repo.get_by_business(business_id)

        if not prefs or not prefs.posting_schedule:
            return {"created": 0, "skipped": 0, "message": "No posting schedule configured"}

        # Need a calendar to anchor slots to; find or create for the month
        cal_repo = CalendarRepository(self.session)
        stmt = select(cal_repo.model).where(
            and_(
                cal_repo.model.business_id == business_id,
                cal_repo.model.month == month,
                cal_repo.model.year == year,
            )
        )
        from sqlalchemy import select as sa_select
        result = await self.session.execute(
            sa_select(cal_repo.model).where(
                and_(
                    cal_repo.model.business_id == business_id,
                    cal_repo.model.month == month,
                    cal_repo.model.year == year,
                )
            )
        )
        calendar = result.scalar_one_or_none()
        if not calendar:
            calendar = await cal_repo.create(business_id=business_id, month=month, year=year)

        # Get active platform connections
        conn_result = await self.session.execute(
            select(SocialPlatformConnection).where(
                and_(
                    SocialPlatformConnection.business_id == business_id,
                    SocialPlatformConnection.is_active.is_(True),
                )
            )
        )
        connections = conn_result.scalars().all()
        platforms = [c.platform for c in connections] or ["instagram"]

        timezone_str = business.timezone or "UTC"
        created = 0
        skipped = 0

        for entry in prefs.posting_schedule:
            package_item_id = entry.get("package_item_id")
            for slot_def in entry.get("slots", []):
                day_name = slot_def.get("day", "").lower()
                time_str = slot_def.get("time", "09:00")
                target_weekday = WEEKDAY_NAMES.get(day_name)
                if target_weekday is None:
                    continue

                h, m = map(int, time_str.split(":"))
                days_in_month = cal_module.monthrange(year, month)[1]

                for day_num in range(1, days_in_month + 1):
                    date_obj = datetime(year, month, day_num)
                    if date_obj.weekday() != target_weekday:
                        continue

                    scheduled_at = date_obj.replace(
                        hour=h, minute=m, second=0, microsecond=0, tzinfo=timezone.utc
                    )
                    date_str = f"{year:04d}-{month:02d}-{day_num:02d}"

                    for platform in platforms:
                        existing = await slot_repo.get_by_business_and_time(
                            business_id, scheduled_at
                        )
                        if existing:
                            if existing.status in ("approved", "published"):
                                skipped += 1
                                continue
                            skipped += 1
                            continue

                        slot = ContentSlot(
                            calendar_id=calendar.id,
                            business_id=business_id,
                            platform=platform,
                            status="empty",
                            scheduled_at=scheduled_at,
                        )
                        self.session.add(slot)
                        created += 1

        if created:
            await self.session.flush()

        logger.info(
            "sync_slots_complete",
            business_id=business_id,
            month=month,
            year=year,
            created=created,
            skipped=skipped,
        )
        return {"created": created, "skipped": skipped}

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
