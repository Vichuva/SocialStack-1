from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from socialstack.api.superone.deps import RequestContext, envelope, paginated, get_context
from socialstack.dependencies import DbSession
from socialstack.db.models.content import ContentSlot, ContentVariant
from socialstack.repositories.business_repo import BusinessPreferencesRepository
from socialstack.repositories.content_repo import ContentSlotRepository, ContentVariantRepository
from socialstack.utils.errors import NotFoundError

router = APIRouter(tags=["slots"])
Ctx = Annotated[RequestContext, Depends(get_context)]


# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt_slot(slot, has_variants: bool = False) -> dict:
    date = slot.scheduled_at.strftime("%Y-%m-%d") if slot.scheduled_at else None
    return {
        "id": slot.id,
        "date": date,
        "scheduled_at": slot.scheduled_at.isoformat() if slot.scheduled_at else None,
        "theme": getattr(slot, "theme", None),
        "objective": getattr(slot, "objective", None),
        "problem": slot.problem,
        "solution": slot.solution,
        "impact": slot.impact,
        "status": slot.status,
        "package_item_id": getattr(slot, "package_item_id", None),
        "generation_attempt": slot.generation_attempt,
        "approved_at": slot.approved_at.isoformat() if slot.approved_at else None,
        "created_at": slot.created_at.isoformat() if slot.created_at else None,
        "has_variants": has_variants,
    }


def _fmt_variant(v) -> dict:
    return {
        "id": v.id,
        "platform": v.platform,
        "platform_connection_id": getattr(v, "platform_connection_id", None),
        "content": v.content or v.caption,
        "asset_url": None,
        "asset_type": None,
        "asset_source": None,
        "version": v.version,
        "is_current": v.is_current,
        "is_active": v.is_active,
        "review_status": v.review_status,
        "feedback_text": v.feedback_text,
        "generation_metadata": v.generation_metadata or {},
        "regeneration_count": v.regeneration_count,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


async def _get_slot_or_404(slot_id: str, business_id: str, db) -> ContentSlot:
    repo = ContentSlotRepository(db)
    slot = await repo.get(slot_id)
    if not slot or slot.business_id != business_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Slot not found", "status": 404},
        )
    return slot


# ── 3.1 POST /content/slots/sync ─────────────────────────────────────────────

class SyncSlotsBody(BaseModel):
    posting_schedule: list[dict]


@router.post("/slots/sync")
async def sync_slots(ctx: Ctx, body: SyncSlotsBody, db: DbSession):
    prefs_repo = BusinessPreferencesRepository(db)
    await prefs_repo.upsert(ctx.business_id, posting_schedule=body.posting_schedule)

    from socialstack.ai.client import get_ai_client
    from socialstack.services.calendar_service import CalendarService
    ai = get_ai_client()
    svc = CalendarService(db, ai)

    from datetime import date
    today = date.today()
    total_created = total_updated = total_deleted = total_preserved = 0
    for months_ahead in range(3):
        mo = today.month + months_ahead
        yr = today.year + (mo - 1) // 12
        mo = ((mo - 1) % 12) + 1
        result = await svc.sync_slots_from_schedule(
            business_id=ctx.business_id, month=mo, year=yr
        )
        total_created += result.get("created", 0)
        total_preserved += result.get("skipped", 0)

    return envelope(
        {"created": total_created, "updated": total_updated, "deleted": total_deleted, "preserved": total_preserved},
        ctx.request_id,
    )


# ── 3.2 GET /content/slots?month=&year= ───────────────────────────────────────

@router.get("/slots")
async def list_slots(
    ctx: Ctx,
    db: DbSession,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020, le=2100),
    limit: int = Query(100, ge=1, le=200),
    cursor: str | None = Query(None),
):
    stmt = (
        select(ContentSlot)
        .where(
            and_(
                ContentSlot.business_id == ctx.business_id,
                ContentSlot.scheduled_at != None,  # noqa: E711
            )
        )
        .order_by(ContentSlot.scheduled_at.asc())
    )
    result = await db.execute(stmt)
    all_slots = result.scalars().all()

    # Filter to the requested month/year
    filtered = [
        s for s in all_slots
        if s.scheduled_at and s.scheduled_at.month == month and s.scheduled_at.year == year
    ]

    # Check which slots have current active variants
    slot_ids = [s.id for s in filtered]
    variant_slot_ids: set[str] = set()
    if slot_ids:
        vstmt = select(ContentVariant.slot_id).where(
            and_(
                ContentVariant.slot_id.in_(slot_ids),
                ContentVariant.is_current.is_(True),
                ContentVariant.is_active.is_(True),
            )
        ).distinct()
        vresult = await db.execute(vstmt)
        variant_slot_ids = {row[0] for row in vresult.all()}

    items = [_fmt_slot(s, has_variants=s.id in variant_slot_ids) for s in filtered[:limit]]
    return paginated(items, total=len(filtered), has_more=len(filtered) > limit)


# ── 3.3 GET /content/slots/{slot_id} ─────────────────────────────────────────

@router.get("/slots/{slot_id}")
async def get_slot(ctx: Ctx, slot_id: str, db: DbSession):
    stmt = (
        select(ContentSlot)
        .options(selectinload(ContentSlot.variants))
        .where(ContentSlot.id == slot_id)
    )
    result = await db.execute(stmt)
    slot = result.scalar_one_or_none()
    if not slot or slot.business_id != ctx.business_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Slot not found", "status": 404},
        )

    current_variants = [v for v in slot.variants if v.is_current and v.is_active]
    data = {**_fmt_slot(slot), "variants": [_fmt_variant(v) for v in current_variants]}
    return envelope(data, ctx.request_id)


# ── 3.4 PATCH /content/slots/{slot_id} ───────────────────────────────────────

class SlotUpdateBody(BaseModel):
    theme: str | None = None
    objective: str | None = None
    problem: str | None = None
    solution: str | None = None
    impact: str | None = None


@router.patch("/slots/{slot_id}")
async def update_slot(ctx: Ctx, slot_id: str, body: SlotUpdateBody, db: DbSession):
    slot = await _get_slot_or_404(slot_id, ctx.business_id, db)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        repo = ContentSlotRepository(db)
        slot = await repo.update(slot, **updates)
    return envelope(_fmt_slot(slot), ctx.request_id)


# ── 4.1 POST /content/slots/generate-themes ──────────────────────────────────

class GenerateThemesBody(BaseModel):
    month: int
    year: int


@router.post("/slots/generate-themes")
async def generate_themes(ctx: Ctx, body: GenerateThemesBody, db: DbSession):
    from socialstack.services.slot_generation_service import SlotGenerationService
    svc = SlotGenerationService(db)
    result = await svc.generate_themes(
        business_id=ctx.business_id, month=body.month, year=body.year
    )
    return envelope(result, ctx.request_id)


# ── 4.2 POST /content/slots/generate-variants (batch) ────────────────────────

class GenerateVariantsBody(BaseModel):
    month: int
    year: int


@router.post("/slots/generate-variants")
async def generate_variants_batch(ctx: Ctx, body: GenerateVariantsBody, db: DbSession):
    from socialstack.services.slot_generation_service import SlotGenerationService
    svc = SlotGenerationService(db)
    result = await svc.generate_variants(
        business_id=ctx.business_id, month=body.month, year=body.year
    )
    return envelope(result, ctx.request_id)


# ── 4.3 POST /content/slots/{slot_id}/generate-variants ──────────────────────

class RegenerateVariantsBody(BaseModel):
    platforms: list[str] | None = None
    feedback: str | None = None


@router.post("/slots/{slot_id}/generate-variants")
async def generate_variants_for_slot(
    ctx: Ctx, slot_id: str, body: RegenerateVariantsBody, db: DbSession
):
    slot = await _get_slot_or_404(slot_id, ctx.business_id, db)
    from socialstack.services.slot_generation_service import SlotGenerationService
    svc = SlotGenerationService(db)
    result = await svc.generate_variants_for_slot(
        slot=slot,
        platforms=body.platforms,
        feedback=body.feedback,
    )
    return envelope(result, ctx.request_id)


# ── 5.6 POST /content/slots/approve-all ──────────────────────────────────────

class ApproveAllBody(BaseModel):
    month: int | None = None
    year: int | None = None


@router.post("/slots/approve-all")
async def approve_all(ctx: Ctx, body: ApproveAllBody, db: DbSession):
    from socialstack.services.approval_service import ApprovalService
    svc = ApprovalService(db)
    result = await svc.approve_all(business_id=ctx.business_id)
    return envelope(result, ctx.request_id)


# ── 5.7 POST /content/slots/{slot_id}/send-back ──────────────────────────────

@router.post("/slots/{slot_id}/send-back")
async def send_back(ctx: Ctx, slot_id: str, db: DbSession):
    slot = await _get_slot_or_404(slot_id, ctx.business_id, db)
    now = datetime.now(timezone.utc)
    if slot.scheduled_at and slot.scheduled_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "slot_in_past", "message": "Cannot send back a past slot", "status": 400},
        )

    slot_repo = ContentSlotRepository(db)
    variant_repo = ContentVariantRepository(db)
    variants = await variant_repo.get_current_for_slot(slot_id)
    for v in variants:
        await variant_repo.update(v, review_status="pending")
    await slot_repo.update(slot, status="pending_review", approved_at=None)
    return envelope({"sent_back": True}, ctx.request_id)


# ── 5.8 POST /content/slots/{slot_id}/publish ────────────────────────────────

@router.post("/slots/{slot_id}/publish")
async def publish_slot(ctx: Ctx, slot_id: str, db: DbSession):
    slot = await _get_slot_or_404(slot_id, ctx.business_id, db)
    if slot.status not in ("approved", "pending_review"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_status", "message": f"Slot status is '{slot.status}', cannot publish", "status": 400},
        )
    slot_repo = ContentSlotRepository(db)
    variant_repo = ContentVariantRepository(db)
    variants = await variant_repo.get_current_for_slot(slot_id)
    for v in variants:
        await variant_repo.update(v, review_status="approved")
    await slot_repo.update(slot, status="published")
    return envelope({"published": True}, ctx.request_id)


# ── 8.1 GET /content/slots/{slot_id}/status ──────────────────────────────────

@router.get("/slots/{slot_id}/status")
async def get_slot_status(ctx: Ctx, slot_id: str, db: DbSession):
    slot = await _get_slot_or_404(slot_id, ctx.business_id, db)
    return envelope(
        {"id": slot.id, "status": slot.status, "generation_attempt": slot.generation_attempt},
        ctx.request_id,
    )


# ── 6.1 GET /content/slots/{slot_id}/variants ────────────────────────────────

@router.get("/slots/{slot_id}/variants")
async def list_slot_variants(
    ctx: Ctx,
    slot_id: str,
    db: DbSession,
    platform: str | None = Query(None),
    include_inactive: bool = Query(True),
):
    slot = await _get_slot_or_404(slot_id, ctx.business_id, db)
    stmt = (
        select(ContentVariant)
        .where(ContentVariant.slot_id == slot_id)
        .order_by(ContentVariant.version.asc())
    )
    if platform:
        stmt = stmt.where(ContentVariant.platform == platform)
    if not include_inactive:
        stmt = stmt.where(ContentVariant.is_active.is_(True))
    result = await db.execute(stmt)
    variants = result.scalars().all()
    return envelope([_fmt_variant(v) for v in variants], ctx.request_id)
