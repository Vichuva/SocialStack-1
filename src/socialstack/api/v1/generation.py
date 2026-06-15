from fastapi import APIRouter

from socialstack.dependencies import DbSession
from socialstack.schemas.generation import (
    AssetRequest,
    BriefRequest,
    CaptionRequest,
    MultiVariantRequest,
    OrchestrateRequest,
    RegenerateRequest,
    TaskResponse,
)
from socialstack.schemas.publish import ReviewRejectRequest
from socialstack.services.run_service import RunService

router = APIRouter(tags=["generation"])


@router.post("/orchestrate", response_model=TaskResponse)
async def orchestrate(body: OrchestrateRequest, db: DbSession):
    run_svc = RunService(db)
    run = await run_svc.create(
        workflow="WF-GENORCH",
        business_id=body.business_id,
        trigger_kind="api",
        input_data=body.model_dump(),
    )
    from socialstack.tasks.generation_tasks import generate_content_task
    generate_content_task.delay(
        calendar_id=body.calendar_id,
        business_id=body.business_id,
        platforms=[p.value for p in body.platforms],
        generate_images=body.generate_images,
        run_id=run.id,
    )
    return TaskResponse(run_id=run.id)


@router.post("/brief", response_model=TaskResponse)
async def generate_brief(body: BriefRequest, db: DbSession):
    run_svc = RunService(db)
    run = await run_svc.create(
        workflow="WF-BRIEF",
        business_id=body.business_id,
        trigger_kind="api",
        input_data=body.model_dump(),
    )
    from socialstack.tasks.generation_tasks import generate_brief_task
    generate_brief_task.delay(
        slot_id=body.slot_id,
        business_id=body.business_id,
        day=body.day,
        run_id=run.id,
    )
    return TaskResponse(run_id=run.id)


@router.post("/caption", response_model=TaskResponse)
async def generate_caption(body: CaptionRequest, db: DbSession):
    run_svc = RunService(db)
    run = await run_svc.create(
        workflow="WF-CAPTION",
        business_id=body.business_id,
        trigger_kind="api",
        input_data=body.model_dump(),
    )
    from socialstack.tasks.generation_tasks import generate_caption_task
    generate_caption_task.delay(
        slot_id=body.slot_id,
        business_id=body.business_id,
        platform=body.platform.value,
        brief=body.brief.model_dump(),
        run_id=run.id,
    )
    return TaskResponse(run_id=run.id)


@router.post("/asset", response_model=TaskResponse)
async def generate_asset(body: AssetRequest, db: DbSession):
    run_svc = RunService(db)
    run = await run_svc.create(
        workflow="WF-ASSET",
        business_id=body.business_id,
        trigger_kind="api",
        input_data=body.model_dump(),
    )
    from socialstack.tasks.generation_tasks import generate_asset_task
    generate_asset_task.delay(
        slot_id=body.slot_id,
        business_id=body.business_id,
        platform=body.platform.value,
        theme=body.theme,
        brief=body.brief.model_dump(),
        run_id=run.id,
    )
    return TaskResponse(run_id=run.id)


@router.post("/multi-variant", response_model=TaskResponse)
async def generate_multi_variant(body: MultiVariantRequest, db: DbSession):
    run_svc = RunService(db)
    run = await run_svc.create(
        workflow="WF-MVAR",
        business_id=body.business_id,
        trigger_kind="api",
        input_data=body.model_dump(),
    )
    from socialstack.tasks.generation_tasks import generate_multi_variant_task
    generate_multi_variant_task.delay(
        slot_id=body.slot_id,
        business_id=body.business_id,
        platform=body.platform.value,
        brief=body.brief.model_dump(),
        variant_count=body.variant_count,
        run_id=run.id,
    )
    return TaskResponse(run_id=run.id)


@router.post("/regenerate", response_model=TaskResponse)
async def regenerate(body: RegenerateRequest, db: DbSession):
    run_svc = RunService(db)
    run = await run_svc.create(
        workflow="WF-REGEN",
        business_id=body.business_id,
        trigger_kind="api",
        input_data=body.model_dump(),
    )
    from socialstack.tasks.regeneration_tasks import regenerate_content_task
    regenerate_content_task.delay(
        slot_id=body.slot_id,
        business_id=body.business_id,
        platform=body.platform.value,
        feedback=body.feedback,
        original_brief=body.original_brief.model_dump(),
        run_id=run.id,
    )
    return TaskResponse(run_id=run.id)
