from sqlalchemy import and_, select

from socialstack.db.models.metrics import PostMetrics
from socialstack.repositories.base import BaseRepository


class PostMetricsRepository(BaseRepository[PostMetrics]):
    model = PostMetrics

    async def get_by_business(
        self,
        business_id: str,
        platform: str | None = None,
        limit: int = 100,
    ) -> list[PostMetrics]:
        stmt = (
            select(PostMetrics)
            .where(PostMetrics.business_id == business_id)
            .order_by(PostMetrics.collected_at.desc())
            .limit(limit)
        )
        if platform:
            stmt = stmt.where(PostMetrics.platform == platform)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
