from sqlalchemy import and_, select

from socialstack.db.models.publish import PublishEvent
from socialstack.repositories.base import BaseRepository


class PublishEventRepository(BaseRepository[PublishEvent]):
    model = PublishEvent

    async def get_successful_for_metrics(self, business_id: str | None = None) -> list[PublishEvent]:
        stmt = select(PublishEvent).where(PublishEvent.status == "success")
        if business_id:
            stmt = stmt.where(PublishEvent.business_id == business_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_slot(self, slot_id: str) -> list[PublishEvent]:
        stmt = (
            select(PublishEvent)
            .where(PublishEvent.slot_id == slot_id)
            .order_by(PublishEvent.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
