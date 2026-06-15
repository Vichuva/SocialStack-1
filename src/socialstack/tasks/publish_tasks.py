import asyncio

from socialstack.celery_app import celery_app
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


def _run(coro):
    return asyncio.run(coro)


@celery_app.task(
    bind=True,
    name="socialstack.tasks.publish_tasks.publish_slot_task",
    queue="publishing",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def publish_slot_task(self, slot_id: str, run_id: str | None = None):
    async def _inner():
        from socialstack.db.session import get_sessionmaker
        from socialstack.services.publish_service import PublishService
        from socialstack.services.run_service import RunService
        from socialstack.utils.idempotency import acquire_publish_lock, release_publish_lock
        from socialstack.utils.errors import RateLimitError

        async with get_sessionmaker()() as session:
            locked = await acquire_publish_lock(slot_id)
            if not locked:
                logger.warning("publish_skipped_already_locked", slot_id=slot_id)
                return

            run_svc = RunService(session)
            if run_id:
                await run_svc.start(run_id, celery_task_id=self.request.id)

            try:
                svc = PublishService(session)
                result = await svc.publish(slot_id)
                if run_id:
                    await run_svc.succeed(run_id, output=result)
                await release_publish_lock(slot_id)
                await session.commit()
            except RateLimitError as exc:
                if run_id:
                    await run_svc.fail(run_id, error={"message": str(exc)})
                await session.commit()
                raise self.retry(exc=exc, countdown=exc.retry_after_seconds)
            except Exception as exc:
                await release_publish_lock(slot_id)
                if run_id:
                    await run_svc.fail(run_id, error={"message": str(exc)})
                await session.commit()
                raise

    _run(_inner())


@celery_app.task(name="socialstack.tasks.publish_tasks.publish_orchestrator_task", queue="publishing")
def publish_orchestrator_task():
    """WF-PUBORCH: runs every 5 min via Beat, finds due slots, dispatches publish_slot_task per slot."""
    async def _inner():
        from socialstack.db.session import get_sessionmaker
        from socialstack.repositories.content_repo import ContentSlotRepository
        from socialstack.db.session import get_sessionmaker

        async with get_sessionmaker()() as session:
            repo = ContentSlotRepository(session)
            due_slots = await repo.get_due_for_publish()
            logger.info("publish_orchestrator_tick", due_count=len(due_slots))
            for slot in due_slots:
                publish_slot_task.delay(slot_id=slot.id, run_id=None)

    _run(_inner())
