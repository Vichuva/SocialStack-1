from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.repositories.content_repo import ContentSlotRepository, ContentVariantRepository
from socialstack.repositories.publish_repo import PublishEventRepository
from socialstack.utils.errors import NotFoundError, PublishError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class PublishService:
    """WF-PUBLISH: loads the latest approved variant for a slot and publishes it."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def publish(self, slot_id: str) -> dict:
        slot_repo = ContentSlotRepository(self.session)
        variant_repo = ContentVariantRepository(self.session)
        event_repo = PublishEventRepository(self.session)

        slot = await slot_repo.get_or_raise(slot_id)
        variant = await variant_repo.get_latest_for_slot_platform(slot_id, slot.platform)
        if not variant:
            raise NotFoundError("ContentVariant", f"slot={slot_id} platform={slot.platform}")

        # Get media asset URL if exists
        asset_url: str | None = None
        if variant.media_assets:
            asset_url = variant.media_assets[0].storage_url

        # Get decrypted token
        token = await self._get_token(slot.business_id, slot.platform)

        # Build full text
        hashtags = variant.hashtags or []
        full_text = variant.caption
        if hashtags:
            full_text = f"{full_text}\n\n{' '.join(hashtags)}"

        # Dispatch to platform publisher
        publisher = self._get_publisher(slot.platform)
        result = await publisher.publish(
            full_text=full_text,
            asset_url=asset_url,
            token=token,
            platform_account_id=await self._get_account_id(slot.business_id, slot.platform),
        )

        # Record publish event
        now = datetime.now(timezone.utc)
        event = await event_repo.create(
            slot_id=slot_id,
            variant_id=variant.id,
            business_id=slot.business_id,
            platform=slot.platform,
            platform_post_id=result.get("platform_post_id"),
            permalink=result.get("permalink"),
            status="success",
            published_at=now,
            publish_method=result.get("publish_method"),
        )

        # Update slot status
        await slot_repo.update(slot, status="published", published_at=now)

        logger.info("slot_published", slot_id=slot_id, platform=slot.platform, permalink=result.get("permalink"))
        return {"event_id": event.id, "permalink": result.get("permalink")}

    async def _get_token(self, business_id: str, platform: str) -> str:
        from sqlalchemy import select
        from socialstack.db.models.social import SocialPlatformConnection
        from socialstack.utils.encryption import decrypt_token
        from socialstack.config import get_settings

        stmt = select(SocialPlatformConnection).where(
            SocialPlatformConnection.business_id == business_id,
            SocialPlatformConnection.platform == platform,
            SocialPlatformConnection.is_active == True,
        )
        result = await self.session.execute(stmt)
        conn = result.scalar_one_or_none()
        if not conn:
            raise PublishError(
                f"No active {platform} connection for business {business_id}", platform
            )
        settings = get_settings()
        return decrypt_token(conn.access_token_enc, settings.token_encryption_key)

    async def _get_account_id(self, business_id: str, platform: str) -> str:
        from sqlalchemy import select
        from socialstack.db.models.social import SocialPlatformConnection

        stmt = select(SocialPlatformConnection).where(
            SocialPlatformConnection.business_id == business_id,
            SocialPlatformConnection.platform == platform,
            SocialPlatformConnection.is_active == True,
        )
        result = await self.session.execute(stmt)
        conn = result.scalar_one_or_none()
        return conn.platform_account_id if conn else ""

    def _get_publisher(self, platform: str):
        from socialstack.publishers.instagram import InstagramPublisher
        from socialstack.publishers.facebook import FacebookPublisher
        from socialstack.publishers.linkedin import LinkedInPublisher
        from socialstack.publishers.twitter import TwitterPublisher

        publishers = {
            "instagram": InstagramPublisher(),
            "facebook": FacebookPublisher(),
            "linkedin": LinkedInPublisher(),
            "twitter": TwitterPublisher(),
        }
        if platform not in publishers:
            raise PublishError(f"Unsupported platform: {platform}", platform)
        return publishers[platform]
