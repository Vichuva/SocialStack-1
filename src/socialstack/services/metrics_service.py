from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.db.models.social import SocialPlatformConnection
from socialstack.repositories.metrics_repo import PostMetricsRepository
from socialstack.repositories.publish_repo import PublishEventRepository
from socialstack.utils.encryption import decrypt_token
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v21.0"
TWITTER_API_BASE = "https://api.twitter.com/2"
LINKEDIN_API_BASE = "https://api.linkedin.com/v2"


class MetricsService:
    """WF-METRICS: fetches platform insights for each published post and records them."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def collect(self, business_id: str | None = None) -> dict:
        event_repo = PublishEventRepository(self.session)
        metrics_repo = PostMetricsRepository(self.session)

        # Only fetch events that haven't been collected recently (deduped in repo)
        events = await event_repo.get_successful_without_recent_metrics(business_id=business_id)
        collected = 0
        failed = 0
        now = datetime.now(timezone.utc)

        for event in events:
            try:
                token = await self._get_token(event.business_id, event.platform)
                if not token:
                    logger.warning(
                        "metrics_no_token",
                        event_id=event.id,
                        business_id=event.business_id,
                        platform=event.platform,
                    )
                    continue

                insights = await self._fetch_insights(event, token)
                if insights:
                    await metrics_repo.create(
                        publish_event_id=event.id,
                        business_id=event.business_id,
                        platform=event.platform,
                        collected_at=now,
                        **insights,
                    )
                    collected += 1
                    logger.info(
                        "metrics_recorded",
                        event_id=event.id,
                        platform=event.platform,
                        impressions=insights.get("impressions"),
                        engagement_rate=insights.get("engagement_rate"),
                    )
            except Exception as e:
                failed += 1
                logger.warning(
                    "metrics_fetch_failed",
                    event_id=event.id,
                    platform=event.platform,
                    post_id=event.platform_post_id,
                    error=str(e),
                )

        logger.info(
            "metrics_run_complete",
            collected=collected,
            failed=failed,
            total_events=len(events),
            business_id=business_id,
        )
        return {"collected": collected, "failed": failed, "total_events": len(events)}

    async def _get_token(self, business_id: str, platform: str) -> str | None:
        from socialstack.config import get_settings

        stmt = select(SocialPlatformConnection).where(
            SocialPlatformConnection.business_id == business_id,
            SocialPlatformConnection.platform == platform,
            SocialPlatformConnection.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        conn = result.scalar_one_or_none()
        if not conn:
            return None
        settings = get_settings()
        try:
            return decrypt_token(conn.access_token_enc, settings.token_encryption_key)
        except Exception as e:
            logger.warning("metrics_token_decrypt_failed", platform=platform, error=str(e))
            return None

    async def _fetch_insights(self, event, token: str) -> dict | None:
        platform = event.platform
        post_id = event.platform_post_id
        if not post_id:
            return None

        if platform == "instagram":
            return await self._fetch_instagram(post_id, token)
        elif platform == "facebook":
            return await self._fetch_facebook(post_id, token)
        elif platform == "linkedin":
            return await self._fetch_linkedin(post_id, token)
        elif platform == "twitter":
            return await self._fetch_twitter(post_id, token)
        else:
            logger.warning("metrics_unsupported_platform", platform=platform)
            return None

    async def _fetch_instagram(self, media_id: str, token: str) -> dict | None:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{GRAPH_BASE}/{media_id}/insights",
                params={
                    "metric": "impressions,reach,likes,comments,saved,shares",
                    "access_token": token,
                },
            )
        if not resp.is_success:
            logger.warning("instagram_insights_error", media_id=media_id, status=resp.status_code)
            return None

        raw: dict = {}
        for item in resp.json().get("data", []):
            values = item.get("values", [])
            if values:
                raw[item["name"]] = values[0].get("value", 0)

        impressions = raw.get("impressions", 0)
        likes = raw.get("likes", 0)
        comments = raw.get("comments", 0)
        saves = raw.get("saved", 0)
        shares = raw.get("shares", 0)
        engaged = likes + comments + saves + shares

        return {
            "impressions": impressions,
            "reach": raw.get("reach", 0),
            "likes": likes,
            "comments": comments,
            "saves": saves,
            "shares": shares,
            "clicks": None,
            "engagement_rate": round(engaged / impressions, 4) if impressions else 0.0,
        }

    async def _fetch_facebook(self, post_id: str, token: str) -> dict | None:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{GRAPH_BASE}/{post_id}/insights",
                params={
                    "metric": "post_impressions,post_reach,post_reactions_like_total,post_comments,post_shares",
                    "access_token": token,
                },
            )
        if not resp.is_success:
            logger.warning("facebook_insights_error", post_id=post_id, status=resp.status_code)
            return None

        raw: dict = {}
        for item in resp.json().get("data", []):
            values = item.get("values", [])
            if values:
                raw[item["name"]] = values[-1].get("value", 0)

        impressions = raw.get("post_impressions", 0)
        likes = raw.get("post_reactions_like_total", 0)
        comments = raw.get("post_comments", 0)
        shares_raw = raw.get("post_shares", 0)
        shares = shares_raw.get("count", 0) if isinstance(shares_raw, dict) else int(shares_raw or 0)
        engaged = likes + comments + shares

        return {
            "impressions": impressions,
            "reach": raw.get("post_reach", 0),
            "likes": likes,
            "comments": comments,
            "saves": 0,
            "shares": shares,
            "clicks": None,
            "engagement_rate": round(engaged / impressions, 4) if impressions else 0.0,
        }

    async def _fetch_linkedin(self, share_urn: str, token: str) -> dict | None:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{LINKEDIN_API_BASE}/organizationalEntityShareStatistics",
                params={"q": "organizationalEntity", "shares": f"List({share_urn})"},
                headers={"Authorization": f"Bearer {token}", "LinkedIn-Version": "202304"},
            )
        if not resp.is_success:
            logger.warning("linkedin_insights_error", share_urn=share_urn, status=resp.status_code)
            return None

        elements = resp.json().get("elements", [])
        if not elements:
            return None

        stats = elements[0].get("totalShareStatistics", {})
        impressions = stats.get("impressionCount", 0)
        clicks = stats.get("clickCount", 0)
        likes = stats.get("likeCount", 0)
        comments = stats.get("commentCount", 0)
        shares = stats.get("shareCount", 0)
        engaged = likes + comments + shares + clicks

        return {
            "impressions": impressions,
            "reach": impressions,  # LinkedIn doesn't expose reach separately
            "likes": likes,
            "comments": comments,
            "saves": 0,
            "shares": shares,
            "clicks": clicks,
            "engagement_rate": round(engaged / impressions, 4) if impressions else 0.0,
        }

    async def _fetch_twitter(self, tweet_id: str, token: str) -> dict | None:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{TWITTER_API_BASE}/tweets/{tweet_id}",
                params={"tweet.fields": "public_metrics"},
                headers={"Authorization": f"Bearer {token}"},
            )
        if not resp.is_success:
            logger.warning("twitter_insights_error", tweet_id=tweet_id, status=resp.status_code)
            return None

        public_metrics = resp.json().get("data", {}).get("public_metrics", {})
        impressions = public_metrics.get("impression_count", 0)
        likes = public_metrics.get("like_count", 0)
        retweets = public_metrics.get("retweet_count", 0)
        replies = public_metrics.get("reply_count", 0)
        bookmarks = public_metrics.get("bookmark_count", 0)
        engaged = likes + retweets + replies

        return {
            "impressions": impressions,
            "reach": impressions,
            "likes": likes,
            "comments": replies,
            "saves": bookmarks,
            "shares": retweets,
            "clicks": None,
            "engagement_rate": round(engaged / impressions, 4) if impressions else 0.0,
        }
