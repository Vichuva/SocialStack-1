from typing import Protocol


class AbstractPublisher(Protocol):
    async def publish(
        self,
        full_text: str,
        asset_url: str | None,
        token: str,
        platform_account_id: str,
    ) -> dict:
        """Publish content and return {platform_post_id, permalink, publish_method}."""
        ...
