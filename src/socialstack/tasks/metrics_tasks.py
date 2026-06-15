import asyncio

from socialstack.celery_app import celery_app
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


def _run(coro):
    return asyncio.run(coro)


@celery_app.task(name="socialstack.tasks.metrics_tasks.collect_metrics_task", queue="metrics")
def collect_metrics_task(business_id: str | None = None, run_id: str | None = None):
    """WF-METRICS: runs every 6h via Beat. Fetches platform insights for all published posts."""
    async def _inner():
        from socialstack.db.session import get_sessionmaker
        from socialstack.services.metrics_service import MetricsService
        from socialstack.services.run_service import RunService

        async with get_sessionmaker()() as session:
            run_svc = RunService(session)

            local_run_id = run_id
            if not local_run_id:
                run = await run_svc.create(
                    workflow="WF-METRICS",
                    business_id=business_id,
                    trigger_kind="cron",
                )
                local_run_id = run.id

            await run_svc.start(local_run_id)
            try:
                svc = MetricsService(session)
                result = await svc.collect(business_id=business_id)
                await run_svc.succeed(local_run_id, output=result)
                await session.commit()
            except Exception as exc:
                await run_svc.fail(local_run_id, error={"message": str(exc)})
                await session.commit()
                raise

    _run(_inner())
