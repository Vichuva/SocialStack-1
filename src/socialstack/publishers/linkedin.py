import httpx

from socialstack.utils.errors import PublishError, RateLimitError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class LinkedInPublisher:
    async def publish(self, full_text: str, asset_url: str | None, token: str, platform_account_id: str) -> dict:
        # platform_account_id is either person URN or organization URN
        author = platform_account_id if platform_account_id.startswith("urn:") else f"urn:li:person:{platform_account_id}"

        body: dict = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": full_text},
                    "shareMediaCategory": "IMAGE" if asset_url else "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        if asset_url:
            body["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                {"status": "READY", "originalUrl": asset_url}
            ]

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.linkedin.com/v2/ugcPosts",
                json=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            if resp.status_code == 429:
                raise RateLimitError("linkedin", int(resp.headers.get("Retry-After", 300)))
            if not resp.is_success:
                raise PublishError(f"LinkedIn publish failed: {resp.text}", "linkedin", resp.status_code)

            post_id = resp.json().get("id", "")
            permalink = f"https://www.linkedin.com/feed/update/{post_id}/"
            logger.info("linkedin_published", author=author, post_id=post_id)
            return {
                "platform_post_id": post_id,
                "permalink": permalink,
                "publish_method": "linkedin_ugcPosts",
            }
