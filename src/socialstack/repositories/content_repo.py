from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from socialstack.db.models.content import ContentBrief, ContentFeedback, ContentSlot, ContentVariant
from socialstack.repositories.base import BaseRepository


class ContentSlotRepository(BaseRepository[ContentSlot]):
    model = ContentSlot

    async def get_by_calendar(self, calendar_id: str, status: str | None = None) -> list[ContentSlot]:
        stmt = select(ContentSlot).where(ContentSlot.calendar_id == calendar_id)
        if status:
            stmt = stmt.where(ContentSlot.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_due_for_publish(self) -> list[ContentSlot]:
        """Slots that are approved and scheduled_at <= now."""
        now = datetime.now(timezone.utc)
        stmt = select(ContentSlot).where(
            and_(
                ContentSlot.status == "approved",
                ContentSlot.scheduled_at <= now,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_review(self, business_id: str) -> list[ContentSlot]:
        stmt = (
            select(ContentSlot)
            .options(
                selectinload(ContentSlot.variants),
                selectinload(ContentSlot.calendar_day),
            )
            .where(
                and_(
                    ContentSlot.business_id == business_id,
                    ContentSlot.status == "pending_review",
                )
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class ContentBriefRepository(BaseRepository[ContentBrief]):
    model = ContentBrief

    async def get_latest_for_slot(self, slot_id: str) -> ContentBrief | None:
        stmt = (
            select(ContentBrief)
            .where(ContentBrief.slot_id == slot_id)
            .order_by(ContentBrief.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class ContentVariantRepository(BaseRepository[ContentVariant]):
    model = ContentVariant

    async def get_by_slot(self, slot_id: str) -> list[ContentVariant]:
        stmt = (
            select(ContentVariant)
            .where(ContentVariant.slot_id == slot_id)
            .order_by(ContentVariant.version.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_for_slot_platform(
        self, slot_id: str, platform: str
    ) -> ContentVariant | None:
        stmt = (
            select(ContentVariant)
            .where(
                and_(
                    ContentVariant.slot_id == slot_id,
                    ContentVariant.platform == platform,
                )
            )
            .order_by(ContentVariant.version.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_next_version(self, slot_id: str, platform: str) -> int:
        existing = await self.get_latest_for_slot_platform(slot_id, platform)
        return (existing.version + 1) if existing else 1


class ContentFeedbackRepository(BaseRepository[ContentFeedback]):
    model = ContentFeedback

    async def get_by_slot(self, slot_id: str) -> list[ContentFeedback]:
        stmt = (
            select(ContentFeedback)
            .where(ContentFeedback.slot_id == slot_id)
            .order_by(ContentFeedback.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
