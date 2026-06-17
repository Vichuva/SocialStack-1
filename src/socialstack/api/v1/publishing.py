from fastapi import APIRouter, Query
from pydantic import BaseModel

from socialstack.dependencies import DbSession
from socialstack.repositories.content_repo import ContentSlotRepository, ContentVariantRepository
from socialstack.schemas.calendar import SlotResponse
from socialstack.schemas.generation import TaskResponse
from socialstack.schemas.publish import PublishRequest, ReviewRejectRequest
from socialstack.services.approval_service import ApprovalService
from socialstack.services.run_service import RunService
from socialstack.utils.errors import NotFoundError

router = APIRouter(tags=["publishing"])


class VariantRejectRequest(BaseModel):
    feedback: str
    regenerate: bool = True
    platform: str | None = None


class ApproveAllRequest(BaseModel):
    calendar_id: str | None = None


class ContentUpdateRequest(BaseModel):
    content: str


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


# ── Per-variant approval endpoints ──────────────────────────────────────────


@router.patch("/review/variants/{variant_id}/approve")
async def approve_variant(variant_id: str, db: DbSession):
    """Approve a single platform variant. Slot auto-promotes when all variants approved."""
    svc = ApprovalService(db)
    return await svc.approve_variant(variant_id)


@router.post("/review/variants/{variant_id}/reject")
async def reject_variant(variant_id: str, body: VariantRejectRequest, db: DbSession):
    """Reject a variant (marks superseded). Optionally triggers regeneration."""
    svc = ApprovalService(db)
    return await svc.reject_variant(
        variant_id=variant_id,
        feedback=body.feedback,
        regenerate=body.regenerate,
        platform=body.platform,
    )


@router.post("/review/slots/approve-all")
async def approve_all_slots(body: ApproveAllRequest, db: DbSession, business_id: str = Query(...)):
    """Bulk-approve all pending_review slots for a business (optionally filtered by calendar)."""
    svc = ApprovalService(db)
    return await svc.approve_all(business_id=business_id, calendar_id=body.calendar_id)


@router.patch("/variants/{variant_id}/content")
async def update_variant_content(variant_id: str, body: ContentUpdateRequest, db: DbSession):
    """Inline caption edit — updates both content and caption fields."""
    repo = ContentVariantRepository(db)
    variant = await repo.get(variant_id)
    if not variant:
        raise NotFoundError("ContentVariant", variant_id)
    await repo.update(variant, content=body.content, caption=body.content)
    return {"updated": True, "variant_id": variant_id}
