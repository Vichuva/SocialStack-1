import httpx

from socialstack.utils.errors import PublishError, RateLimitError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v21.0"


class InstagramPublisher:
    """2-step publish: create media container → publish container."""

    async def publish(self, full_text: str, asset_url: str | None, token: str, platform_account_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Create media container
            create_params: dict = {
                "caption": full_text,
                "access_token": token,
            }
            if asset_url:
                create_params["image_url"] = asset_url
                create_params["media_type"] = "IMAGE"
            else:
                create_params["media_type"] = "REELS"  # fallback without image

            resp = await client.post(f"{GRAPH_BASE}/{platform_account_id}/media", params=create_params)
            if resp.status_code == 429:
                raise RateLimitError("instagram", 300)
            if not resp.is_success:
                raise PublishError(f"Instagram container creation failed: {resp.text}", "instagram", resp.status_code)
            creation_id = resp.json()["id"]

            # Step 2: Publish container
            publish_resp = await client.post(
                f"{GRAPH_BASE}/{platform_account_id}/media_publish",
                params={"creation_id": creation_id, "access_token": token},
            )
            if not publish_resp.is_success:
                raise PublishError(f"Instagram publish failed: {publish_resp.text}", "instagram", publish_resp.status_code)

            media_id = publish_resp.json()["id"]
            permalink = f"https://www.instagram.com/p/{media_id}/"
            logger.info("instagram_published", account=platform_account_id, media_id=media_id)
            return {
                "platform_post_id": media_id,
                "permalink": permalink,
                "publish_method": "instagram_graph_api_2step",
            }
