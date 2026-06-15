from sqlalchemy import select

from socialstack.db.models.schedule import SlotScheduleTemplate
from socialstack.repositories.base import BaseRepository


class SlotScheduleTemplateRepository(BaseRepository[SlotScheduleTemplate]):
    model = SlotScheduleTemplate

    async def list_for_business(self, business_id: str, active_only: bool = True) -> list[SlotScheduleTemplate]:
        stmt = select(SlotScheduleTemplate).where(SlotScheduleTemplate.business_id == business_id)
        if active_only:
            stmt = stmt.where(SlotScheduleTemplate.is_active.is_(True))
        stmt = stmt.order_by(SlotScheduleTemplate.day_of_week, SlotScheduleTemplate.post_time)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
