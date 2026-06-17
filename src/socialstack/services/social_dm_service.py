from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.db.models.social import SocialPlatformConnection
from socialstack.repositories.dm_repo import SocialConversationRepository, SocialMessageRepository
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class SocialDmService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.conv_repo = SocialConversationRepository(session)
        self.msg_repo = SocialMessageRepository(session)

    async def receive_inbound(
        self,
        platform: str,
        sender_id: str,
        sender_name: str | None,
        text: str,
        timestamp: str | None = None,
    ) -> dict:
        """Store an inbound social DM. Always returns {"received": true} — never raises."""
        try:
            # Find the business that owns this platform connection
            result = await self.session.execute(
                select(SocialPlatformConnection).where(
                    and_(
                        SocialPlatformConnection.platform == platform,
                        SocialPlatformConnection.is_active.is_(True),
                    )
                )
            )
            connection = result.scalars().first()
            if not connection:
                logger.warning(
                    "inbound_dm_no_connection", platform=platform, sender_id=sender_id
                )
                return {"received": True}

            business_id = connection.business_id
            conv, created = await self.conv_repo.get_or_create(
                business_id=business_id,
                platform=platform,
                sender_id=sender_id,
                sender_name=sender_name,
            )

            sent_at = None
            if timestamp:
                try:
                    sent_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    sent_at = datetime.now(timezone.utc)
            else:
                sent_at = datetime.now(timezone.utc)

            await self.msg_repo.create(
                conversation_id=conv.id,
                business_id=business_id,
                role="user",
                content=text,
                sent_at=sent_at,
            )

            logger.info(
                "inbound_dm_received",
                platform=platform,
                sender_id=sender_id,
                conversation_id=conv.id,
                new_conversation=created,
            )
        except Exception as exc:
            logger.error("inbound_dm_error", error=str(exc), platform=platform)

        return {"received": True}

    async def reply(self, conversation_id: str, content: str) -> dict:
        """Store an outbound reply. Actual platform delivery is a future stub."""
        conv = await self.conv_repo.get(conversation_id)
        if not conv:
            return {"sent": False, "error": "conversation_not_found"}

        await self.msg_repo.create(
            conversation_id=conversation_id,
            business_id=conv.business_id,
            role="assistant",
            content=content,
            sent_at=datetime.now(timezone.utc),
        )

        logger.info(
            "dm_reply_stored",
            conversation_id=conversation_id,
            content_preview=content[:50],
        )
        return {"sent": True}

    async def list_conversations(
        self,
        business_id: str,
        platform: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list:
        convs = await self.conv_repo.list_for_business(
            business_id=business_id,
            platform=platform,
            status=status,
            limit=limit,
        )
        return [
            {
                "id": c.id,
                "business_id": c.business_id,
                "platform": c.platform,
                "sender_id": c.sender_id,
                "sender_name": c.sender_name,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in convs
        ]

    async def get_messages(self, conversation_id: str) -> list:
        conv = await self.conv_repo.get_with_messages(conversation_id)
        if not conv:
            return []
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            }
            for m in conv.messages
        ]
