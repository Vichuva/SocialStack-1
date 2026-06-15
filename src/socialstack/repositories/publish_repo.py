from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select

from socialstack.db.models.publish import PublishEvent
from socialstack.repositories.base import BaseRepository


class PublishEventRepository(BaseRepository[PublishEvent]):
    model = PublishEvent

    async def get_successful_without_recent_metrics(
        self,
        business_id: str | None = None,
        recollect_after_hours: int = 6,
    ) -> list[PublishEvent]:
        """Return published events that either have no metrics yet, or whose last
        metrics collection was more than recollect_after_hours ago."""
        from socialstack.db.models.metrics import PostMetrics

        cutoff = datetime.now(timezone.utc) - timedelta(hours=recollect_after_hours)

        # Subquery: latest collected_at per publish_event
        subq = (
            select(
                PostMetrics.publish_event_id,
                func.max(PostMetrics.collected_at).label("last_collected"),
            )
            .group_by(PostMetrics.publish_event_id)
            .subquery()
        )

        stmt = (
            select(PublishEvent)
            .outerjoin(subq, PublishEvent.id == subq.c.publish_event_id)
            .where(
                PublishEvent.status == "success",
                PublishEvent.platform_post_id.isnot(None),
                or_(
                    subq.c.last_collected.is_(None),
                    subq.c.last_collected < cutoff,
                ),
            )
            .order_by(PublishEvent.published_at.asc())
        )
        if business_id:
            stmt = stmt.where(PublishEvent.business_id == business_id)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # Kept for backwards compatibility with any direct callers
    async def get_successful_for_metrics(self, business_id: str | None = None) -> list[PublishEvent]:
        return await self.get_successful_without_recent_metrics(business_id=business_id)

    async def get_by_slot(self, slot_id: str) -> list[PublishEvent]:
        stmt = (
            select(PublishEvent)
            .where(PublishEvent.slot_id == slot_id)
            .order_by(PublishEvent.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
