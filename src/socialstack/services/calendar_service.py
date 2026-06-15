import calendar as cal_module

from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.ai.client import AIClient, parse_json_response
from socialstack.repositories.calendar_repo import CalendarDayRepository, CalendarRepository
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
            brand_tone=ctx.brand_tone,
            pain_points=ctx.pain_points,
            offerings=[],  # TODO: load from offerings table when added
            month=calendar.month,
            year=calendar.year,
        )

        raw = await self.ai.chat(prompt)
        themes = parse_json_response(raw, provider="openai")

        if not isinstance(themes, list) or not themes:
            raise ValidationError("AI returned empty or invalid themes array")

        days_in_month = cal_module.monthrange(calendar.year, calendar.month)[1]

        saved = 0
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
                await day_repo.update(
                    existing,
                    theme=item.get("theme"),
                    objective=objective,
                    post_idea=item.get("post_idea"),
                )
            else:
                await day_repo.create(
                    calendar_id=calendar_id,
                    date=date_str,
                    day_number=day_num,
                    theme=item.get("theme"),
                    objective=objective,
                    post_idea=item.get("post_idea"),
                )
            saved += 1

        await cal_repo.update(calendar, status="themes_generated")

        logger.info("calendar_themes_generated", calendar_id=calendar_id, days_saved=saved)
        return {"calendar_id": calendar_id, "days_generated": saved}
