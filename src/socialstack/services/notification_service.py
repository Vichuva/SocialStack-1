from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.db.models.notification import Notification
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class NotificationService:
    """WF-NOTIFY: routes notifications by type and logs them."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def send(self, business_id: str | None, notification_type: str, payload: dict) -> Notification:
        notif = Notification(
            business_id=business_id,
            type=notification_type,
            payload=payload,
            status="pending",
        )
        self.session.add(notif)
        await self.session.flush()

        try:
            await self._deliver(notif)
            notif.status = "sent"
            logger.info("notification_sent", type=notification_type, business_id=business_id)
        except Exception as e:
            notif.status = "failed"
            notif.error_message = str(e)
            logger.warning("notification_failed", type=notification_type, error=str(e))

        await self.session.flush()
        return notif

    async def _deliver(self, notif: Notification) -> None:
        # TODO: implement real delivery channels (webhook, Slack, email)
        # For now, logging is sufficient for dev
        logger.info(
            "notification",
            type=notif.type,
            business_id=notif.business_id,
            payload=notif.payload,
        )
