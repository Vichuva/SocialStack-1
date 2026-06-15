from fastapi import APIRouter, Query

from socialstack.dependencies import DbSession
from socialstack.repositories.metrics_repo import PostMetricsRepository
from socialstack.schemas.generation import TaskResponse
from socialstack.schemas.metrics import CollectMetricsRequest, MetricsResponse
from socialstack.services.run_service import RunService

router = APIRouter(tags=["metrics"])


@router.post("/collect", response_model=TaskResponse)
async def collect_metrics(body: CollectMetricsRequest, db: DbSession):
    run_svc = RunService(db)
    run = await run_svc.create(
        workflow="WF-METRICS",
        business_id=body.business_id,
        trigger_kind="api",
        input_data=body.model_dump(),
    )
    from socialstack.tasks.metrics_tasks import collect_metrics_task
    collect_metrics_task.delay(business_id=body.business_id, run_id=run.id)
    return TaskResponse(run_id=run.id)


@router.get("", response_model=list[MetricsResponse])
async def get_metrics(
    db: DbSession,
    business_id: str = Query(...),
    platform: str | None = Query(None),
    limit: int = Query(default=100, le=500),
):
    repo = PostMetricsRepository(db)
    rows = await repo.get_by_business(business_id, platform=platform, limit=limit)
    return [
        MetricsResponse(
            id=r.id,
            publish_event_id=r.publish_event_id,
            business_id=r.business_id,
            platform=r.platform,
            collected_at=r.collected_at.isoformat(),
            impressions=r.impressions,
            reach=r.reach,
            likes=r.likes,
            comments=r.comments,
            saves=r.saves,
            shares=r.shares,
            clicks=r.clicks,
            engagement_rate=r.engagement_rate,
        )
        for r in rows
    ]
