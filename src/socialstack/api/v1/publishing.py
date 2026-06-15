from fastapi import APIRouter, Query

from socialstack.dependencies import DbSession
from socialstack.repositories.content_repo import ContentSlotRepository
from socialstack.schemas.calendar import SlotResponse
from socialstack.schemas.generation import TaskResponse
from socialstack.schemas.publish import PublishRequest, ReviewRejectRequest
from socialstack.services.run_service import RunService

router = APIRouter(tags=["publishing"])


@router.post("/publishing/slot/{slot_id}", response_model=TaskResponse)
async def publish_slot(slot_id: str, body: PublishRequest, db: DbSession):
    repo = ContentSlotRepository(db)
    slot = await repo.get_or_raise(slot_id)

    run_svc = RunService(db)
    run = await run_svc.create(
        workflow="WF-PUBLISH",
        business_id=slot.business_id,
        trigger_kind="api",
        input_data={"slot_id": slot_id},
    )
    from socialstack.tasks.publish_tasks import publish_slot_task
    publish_slot_task.delay(slot_id=slot_id, run_id=run.id)
    return TaskResponse(run_id=run.id)


@router.get("/publishing/queue", response_model=list[SlotResponse])
async def get_publish_queue(db: DbSession):
    repo = ContentSlotRepository(db)
    slots = await repo.get_due_for_publish()
    return [
        SlotResponse(
            id=s.id,
            calendar_id=s.calendar_id,
            business_id=s.business_id,
            platform=s.platform,
            status=s.status,
            scheduled_at=s.scheduled_at.isoformat() if s.scheduled_at else None,
            published_at=s.published_at.isoformat() if s.published_at else None,
        )
        for s in slots
    ]


@router.get("/review/queue", response_model=list[SlotResponse])
async def get_review_queue(db: DbSession, business_id: str = Query(...)):
    repo = ContentSlotRepository(db)
    slots = await repo.get_pending_review(business_id)
    return [
        SlotResponse(
            id=s.id,
            calendar_id=s.calendar_id,
            business_id=s.business_id,
            platform=s.platform,
            status=s.status,
            scheduled_at=s.scheduled_at.isoformat() if s.scheduled_at else None,
            published_at=s.published_at.isoformat() if s.published_at else None,
        )
        for s in slots
    ]


@router.post("/review/slots/{slot_id}/approve", response_model=SlotResponse)
async def approve_slot(slot_id: str, db: DbSession):
    repo = ContentSlotRepository(db)
    slot = await repo.get_or_raise(slot_id)
    slot = await repo.update(slot, status="approved")
    return SlotResponse(
        id=slot.id,
        calendar_id=slot.calendar_id,
        business_id=slot.business_id,
        platform=slot.platform,
        status=slot.status,
        scheduled_at=slot.scheduled_at.isoformat() if slot.scheduled_at else None,
        published_at=slot.published_at.isoformat() if slot.published_at else None,
    )


@router.post("/review/slots/{slot_id}/reject", response_model=TaskResponse)
async def reject_slot(slot_id: str, body: ReviewRejectRequest, db: DbSession):
    repo = ContentSlotRepository(db)
    slot = await repo.get_or_raise(slot_id)

    from socialstack.repositories.content_repo import ContentFeedbackRepository
    fb_repo = ContentFeedbackRepository(db)
    await fb_repo.create(
        slot_id=slot_id,
        variant_id=body.variant_id,
        business_id=slot.business_id,
        feedback=body.feedback,
    )

    if body.regenerate:
        run_svc = RunService(db)
        run = await run_svc.create(
            workflow="WF-REGEN",
            business_id=slot.business_id,
            trigger_kind="api",
            input_data={"slot_id": slot_id, "feedback": body.feedback},
        )
        from socialstack.tasks.regeneration_tasks import regenerate_from_feedback_task
        regenerate_from_feedback_task.delay(
            slot_id=slot_id,
            feedback=body.feedback,
            platform=body.platform.value if body.platform else slot.platform,
            run_id=run.id,
        )
        return TaskResponse(run_id=run.id)
    else:
        await repo.update(slot, status="failed")
        return TaskResponse(run_id="none", status="rejected")
