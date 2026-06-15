from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.db.models.run import WorkflowRun
from socialstack.repositories.run_repo import WorkflowRunRepository


class RunService:
    def __init__(self, session: AsyncSession):
        self.repo = WorkflowRunRepository(session)

    async def create(
        self,
        workflow: str,
        business_id: str | None = None,
        trigger_kind: str = "api",
        input_data: dict | None = None,
        celery_task_id: str | None = None,
    ) -> WorkflowRun:
        return await self.repo.create(
            workflow=workflow,
            business_id=business_id,
            trigger_kind=trigger_kind,
            status="queued",
            input=input_data,
            celery_task_id=celery_task_id,
        )

    async def start(self, run_id: str, celery_task_id: str | None = None) -> WorkflowRun:
        run = await self.repo.get_or_raise(run_id)
        return await self.repo.update(
            run,
            status="running",
            started_at=datetime.now(timezone.utc),
            celery_task_id=celery_task_id,
        )

    async def succeed(self, run_id: str, output: dict | None = None) -> WorkflowRun:
        run = await self.repo.get_or_raise(run_id)
        return await self.repo.update(
            run,
            status="succeeded",
            finished_at=datetime.now(timezone.utc),
            output=output,
        )

    async def fail(self, run_id: str, error: dict | None = None) -> WorkflowRun:
        run = await self.repo.get_or_raise(run_id)
        return await self.repo.update(
            run,
            status="failed",
            finished_at=datetime.now(timezone.utc),
            error=error,
        )
