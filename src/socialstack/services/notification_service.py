import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.db.models.notification import Notification
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)

# Maps notification type → delivery channels and urgency level.
# Derived from WF-NOTIFY routing table.
_ROUTING: dict[str, dict] = {
    "approval_required": {"channels": ["webhook"],         "urgency": "normal"},
    "content_ready":     {"channels": ["webhook"],         "urgency": "low"},
    "publish_success":   {"channels": ["slack"],           "urgency": "low"},
    "publish_failure":   {"channels": ["slack", "webhook"],"urgency": "high"},
    "token_expiration":  {"channels": ["webhook"],         "urgency": "high"},
    "workflow_failure":  {"channels": ["slack", "webhook"],"urgency": "high"},
}


class NotificationService:
    """WF-NOTIFY: persists each notification, then delivers to Slack / outbound webhook."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def send(self, business_id: str | None, notification_type: str, payload: dict) -> Notification:
        route = _ROUTING.get(notification_type, {"channels": ["webhook"], "urgency": "normal"})

        notif = Notification(
            business_id=business_id,
            type=notification_type,
            payload={**payload, "urgency": route["urgency"]},
            status="pending",
            channel=",".join(route["channels"]),
        )
        self.session.add(notif)
        await self.session.flush()

        try:
            await self._deliver(notif, route["channels"])
            notif.status = "sent"
            logger.info("notification_sent", type=notification_type, business_id=business_id)
        except Exception as e:
            notif.status = "failed"
            notif.error_message = str(e)
            logger.warning("notification_failed", type=notification_type, error=str(e))

        await self.session.flush()
        return notif

    async def _deliver(self, notif: Notification, channels: list[str]) -> None:
        from socialstack.config import get_settings
        settings = get_settings()

        errors: list[str] = []
        for channel in channels:
            try:
                if channel == "slack":
                    await self._send_slack(notif, settings.slack_webhook_url)
                elif channel == "webhook":
                    await self._send_webhook(notif, settings.notification_webhook_url)
            except Exception as e:
                errors.append(f"{channel}: {e}")
                logger.warning("notification_channel_failed", channel=channel, error=str(e))

        # Always log — ensures the notification is observable even when delivery fails
        logger.info(
            "notification_delivered",
            type=notif.type,
            business_id=notif.business_id,
            channels=channels,
            payload=notif.payload,
        )

        if errors and len(errors) == len(channels):
            raise RuntimeError(f"All delivery channels failed: {'; '.join(errors)}")

    async def _send_slack(self, notif: Notification, webhook_url: str) -> None:
        if not webhook_url:
            logger.debug("slack_webhook_not_configured", type=notif.type)
            return

        urgency = notif.payload.get("urgency", "normal")
        emoji = ":rotating_light:" if urgency == "high" else ":bell:"

        message = notif.payload.get("message", "")
        context = notif.payload.get("context", {})

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *[{notif.type.upper().replace('_', ' ')}]* {message}",
                },
            }
        ]

        if context:
            field_items = [f"*{k}:* {v}" for k, v in context.items() if v]
            if field_items:
                blocks.append(
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "\n".join(field_items)},
                    }
                )

        if notif.business_id:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"business_id: `{notif.business_id}`"}
                    ],
                }
            )

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json={"blocks": blocks})
            if not resp.is_success:
                raise RuntimeError(f"Slack webhook returned {resp.status_code}: {resp.text[:200]}")

    async def _send_webhook(self, notif: Notification, webhook_url: str) -> None:
        if not webhook_url:
            logger.debug("notification_webhook_not_configured", type=notif.type)
            return

        body = {
            "event": notif.type,
            "business_id": notif.business_id,
            "payload": notif.payload,
            "notification_id": notif.id,
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=body)
            if not resp.is_success:
                raise RuntimeError(f"Notification webhook returned {resp.status_code}: {resp.text[:200]}")
