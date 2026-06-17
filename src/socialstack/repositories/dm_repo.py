from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from socialstack.db.models.dm import SocialConversation, SocialMessage
from socialstack.repositories.base import BaseRepository


class SocialConversationRepository(BaseRepository[SocialConversation]):
    model = SocialConversation

    async def get_or_create(
        self, business_id: str, platform: str, sender_id: str, sender_name: str | None = None
    ) -> tuple[SocialConversation, bool]:
        stmt = select(SocialConversation).where(
            and_(
                SocialConversation.business_id == business_id,
                SocialConversation.platform == platform,
                SocialConversation.sender_id == sender_id,
            )
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing, False
        conv = await self.create(
            business_id=business_id,
            platform=platform,
            sender_id=sender_id,
            sender_name=sender_name,
        )
        return conv, True

    async def list_for_business(
        self,
        business_id: str,
        platform: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[SocialConversation]:
        stmt = select(SocialConversation).where(
            SocialConversation.business_id == business_id
        )
        if platform:
            stmt = stmt.where(SocialConversation.platform == platform)
        if status:
            stmt = stmt.where(SocialConversation.status == status)
        stmt = stmt.order_by(SocialConversation.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_messages(self, conversation_id: str) -> SocialConversation | None:
        stmt = (
            select(SocialConversation)
            .options(selectinload(SocialConversation.messages))
            .where(SocialConversation.id == conversation_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class SocialMessageRepository(BaseRepository[SocialMessage]):
    model = SocialMessage
