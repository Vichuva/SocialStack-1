from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from socialstack.db.models.calendar import Calendar, CalendarDay
from socialstack.repositories.base import BaseRepository


class CalendarRepository(BaseRepository[Calendar]):
    model = Calendar

    async def get_with_days(self, calendar_id: str) -> Calendar | None:
        stmt = (
            select(Calendar)
            .options(selectinload(Calendar.days))
            .where(Calendar.id == calendar_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_month(self, business_id: str, month: int, year: int) -> Calendar | None:
        stmt = select(Calendar).where(
            and_(
                Calendar.business_id == business_id,
                Calendar.month == month,
                Calendar.year == year,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class CalendarDayRepository(BaseRepository[CalendarDay]):
    model = CalendarDay

    async def get_by_calendar(self, calendar_id: str) -> list[CalendarDay]:
        stmt = (
            select(CalendarDay)
            .where(CalendarDay.calendar_id == calendar_id)
            .order_by(CalendarDay.day_number)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_date(self, calendar_id: str, date: str) -> CalendarDay | None:
        stmt = select(CalendarDay).where(
            and_(CalendarDay.calendar_id == calendar_id, CalendarDay.date == date)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
