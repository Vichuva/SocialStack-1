from sqlalchemy import select

from socialstack.db.models.run import WorkflowRun
from socialstack.repositories.base import BaseRepository


class WorkflowRunRepository(BaseRepository[WorkflowRun]):
    model = WorkflowRun

    async def get_by_business(
        self, business_id: str, workflow: str | None = None, limit: int = 20
    ) -> list[WorkflowRun]:
        stmt = (
            select(WorkflowRun)
            .where(WorkflowRun.business_id == business_id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(limit)
        )
        if workflow:
            stmt = stmt.where(WorkflowRun.workflow == workflow)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
