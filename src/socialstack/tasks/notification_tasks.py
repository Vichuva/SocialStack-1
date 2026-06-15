import asyncio

from socialstack.celery_app import celery_app
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


def _run(coro):
    return asyncio.run(coro)


@celery_app.task(name="socialstack.tasks.notification_tasks.send_notification_task", queue="default")
def send_notification_task(business_id: str | None, notification_type: str, payload: dict):
    async def _inner():
        from socialstack.db.session import get_sessionmaker
        from socialstack.services.notification_service import NotificationService

        async with get_sessionmaker()() as session:
            svc = NotificationService(session)
            await svc.send(business_id=business_id, notification_type=notification_type, payload=payload)
            await session.commit()

    _run(_inner())
