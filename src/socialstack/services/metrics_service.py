from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.repositories.publish_repo import PublishEventRepository
from socialstack.repositories.metrics_repo import PostMetricsRepository
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class MetricsService:
    """WF-METRICS: fetches insights for published posts from each platform."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def collect(self, business_id: str | None = None) -> dict:
        event_repo = PublishEventRepository(self.session)
        metrics_repo = PostMetricsRepository(self.session)

        events = await event_repo.get_successful_for_metrics(business_id=business_id)
        collected = 0
        now = datetime.now(timezone.utc)

        for event in events:
            try:
                insights = await self._fetch_insights(event)
                if insights:
                    await metrics_repo.create(
                        publish_event_id=event.id,
                        business_id=event.business_id,
                        platform=event.platform,
                        collected_at=now,
                        **insights,
                    )
                    collected += 1
            except Exception as e:
                logger.warning("metrics_fetch_failed", event_id=event.id, platform=event.platform, error=str(e))

        logger.info("metrics_collected", count=collected, business_id=business_id)
        return {"collected": collected, "total_events": len(events)}

    async def _fetch_insights(self, event) -> dict | None:
        """Platform-specific insights fetch. Returns normalized metrics dict or None."""
        # TODO: implement real platform API calls per publisher
        # Each platform has its own insights endpoint:
        # Instagram/FB: GET /{media_id}/insights
        # LinkedIn: GET /organizationalEntityShareStatistics
        # Twitter: GET /2/tweets/{id}?tweet.fields=public_metrics
        logger.debug("metrics_fetch_stub", platform=event.platform, post_id=event.platform_post_id)
        return None
