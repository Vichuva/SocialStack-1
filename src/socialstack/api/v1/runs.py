from fastapi import APIRouter, Query

from socialstack.dependencies import DbSession
from socialstack.repositories.run_repo import WorkflowRunRepository
from socialstack.schemas.generation import RunResponse

router = APIRouter(tags=["runs"])


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, db: DbSession):
    repo = WorkflowRunRepository(db)
    run = await repo.get_or_raise(run_id)
    return _run_response(run)


@router.get("", response_model=list[RunResponse])
async def list_runs(
    db: DbSession,
    business_id: str = Query(...),
    workflow: str | None = Query(None),
    limit: int = Query(default=20, le=100),
):
    repo = WorkflowRunRepository(db)
    runs = await repo.get_by_business(business_id, workflow=workflow, limit=limit)
    return [_run_response(r) for r in runs]


def _run_response(run) -> RunResponse:
    return RunResponse(
        id=run.id,
        workflow=run.workflow,
        business_id=run.business_id,
        status=run.status,
        started_at=run.started_at.isoformat() if run.started_at else None,
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
        output=run.output,
        error=run.error,
    )
