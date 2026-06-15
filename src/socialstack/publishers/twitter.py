import httpx

from socialstack.utils.errors import PublishError, PublishValidationError, RateLimitError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)

TWITTER_API_BASE = "https://api.twitter.com/2"


class TwitterPublisher:
    async def publish(self, full_text: str, asset_url: str | None, token: str, platform_account_id: str) -> dict:
        if len(full_text) > 280:
            raise PublishValidationError(
                f"Twitter post is {len(full_text)} chars, exceeds 280 limit. Shorten the caption.",
                "twitter",
            )

        body: dict = {"text": full_text[:280]}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{TWITTER_API_BASE}/tweets",
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("x-rate-limit-reset", 900))
                raise RateLimitError("twitter", retry_after)
            if not resp.is_success:
                raise PublishError(f"Twitter publish failed: {resp.text}", "twitter", resp.status_code)

            data = resp.json().get("data", {})
            tweet_id = data.get("id", "")
            permalink = f"https://twitter.com/i/web/status/{tweet_id}"
            logger.info("twitter_published", tweet_id=tweet_id)
            return {
                "platform_post_id": tweet_id,
                "permalink": permalink,
                "publish_method": "twitter_v2_create_tweet",
            }
