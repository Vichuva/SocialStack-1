import httpx

from socialstack.utils.errors import PublishError, RateLimitError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v21.0"


class FacebookPublisher:
    async def publish(self, full_text: str, asset_url: str | None, token: str, platform_account_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            if asset_url:
                endpoint = f"{GRAPH_BASE}/{platform_account_id}/photos"
                params = {"url": asset_url, "caption": full_text, "access_token": token}
            else:
                endpoint = f"{GRAPH_BASE}/{platform_account_id}/feed"
                params = {"message": full_text, "access_token": token}

            resp = await client.post(endpoint, params=params)
            if resp.status_code == 429:
                raise RateLimitError("facebook", 300)
            if not resp.is_success:
                raise PublishError(f"Facebook publish failed: {resp.text}", "facebook", resp.status_code)

            post_id = resp.json().get("id", "")
            permalink = f"https://www.facebook.com/{post_id}"
            logger.info("facebook_published", account=platform_account_id, post_id=post_id)
            return {
                "platform_post_id": post_id,
                "permalink": permalink,
                "publish_method": "facebook_graph_api_photos",
            }
