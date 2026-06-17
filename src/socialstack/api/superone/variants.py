from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from socialstack.api.superone.deps import RequestContext, envelope, get_context
from socialstack.dependencies import DbSession
from socialstack.repositories.content_repo import ContentSlotRepository, ContentVariantRepository
from socialstack.services.approval_service import ApprovalService

router = APIRouter(tags=["variants"])
Ctx = Annotated[RequestContext, Depends(get_context)]


def _fmt_variant(v) -> dict:
    return {
        "id": v.id,
        "platform": v.platform,
        "content": v.content or v.caption,
        "version": v.version,
        "is_current": v.is_current,
        "is_active": v.is_active,
        "review_status": v.review_status,
        "feedback_text": v.feedback_text,
        "regeneration_count": v.regeneration_count,
        "generation_metadata": v.generation_metadata or {},
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


async def _get_variant_or_404(variant_id: str, business_id: str, db):
    repo = ContentVariantRepository(db)
    v = await repo.get(variant_id)
    if not v or v.business_id != business_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Variant not found", "status": 404},
        )
    return v


# ── 5.1 PATCH /content/variants/{id} — edit caption ─────────────────────────

class VariantUpdateBody(BaseModel):
    content: str


@router.patch("/variants/{variant_id}")
async def update_variant(ctx: Ctx, variant_id: str, body: VariantUpdateBody, db: DbSession):
    v = await _get_variant_or_404(variant_id, ctx.business_id, db)
    repo = ContentVariantRepository(db)
    v = await repo.update(v, content=body.content, caption=body.content, review_status="pending")

    # If slot was approved, revert to pending_review
    slot_repo = ContentSlotRepository(db)
    slot = await slot_repo.get(v.slot_id)
    if slot and slot.status == "approved":
        await slot_repo.update(slot, status="pending_review", approved_at=None)

    return envelope(_fmt_variant(v), ctx.request_id)


# ── 5.2 POST /content/variants/{id}/approve ──────────────────────────────────

@router.post("/variants/{variant_id}/approve")
async def approve_variant(ctx: Ctx, variant_id: str, db: DbSession):
    await _get_variant_or_404(variant_id, ctx.business_id, db)
    svc = ApprovalService(db)
    result = await svc.approve_variant(variant_id)
    return envelope(result, ctx.request_id)


# ── 5.3 POST /content/variants/{id}/reject ───────────────────────────────────

class RejectBody(BaseModel):
    feedback: str = ""
    regenerate: bool = False


@router.post("/variants/{variant_id}/reject")
async def reject_variant(ctx: Ctx, variant_id: str, body: RejectBody, db: DbSession):
    v = await _get_variant_or_404(variant_id, ctx.business_id, db)
    svc = ApprovalService(db)
    result = await svc.reject_variant(
        variant_id=variant_id,
        feedback=body.feedback,
        regenerate=body.regenerate,
        platform=v.platform,
    )
    return envelope(result, ctx.request_id)


# ── 5.4 POST /content/variants/{id}/restore ──────────────────────────────────

@router.post("/variants/{variant_id}/restore")
async def restore_variant(ctx: Ctx, variant_id: str, db: DbSession):
    v = await _get_variant_or_404(variant_id, ctx.business_id, db)
    variant_repo = ContentVariantRepository(db)
    slot_repo = ContentSlotRepository(db)

    # Demote current variant for same slot+platform
    current = await variant_repo.get_current_for_slot_platform(v.slot_id, v.platform)
    if current and current.id != variant_id:
        await variant_repo.update(current, is_current=False)

    # Restore requested variant
    await variant_repo.update(v, is_current=True, is_active=True, review_status="pending")

    # Revert slot status
    slot = await slot_repo.get(v.slot_id)
    if slot and slot.status == "approved":
        await slot_repo.update(slot, status="pending_review", approved_at=None)

    return envelope({"restored": True, "version": v.version}, ctx.request_id)


# ── 5.5 PATCH /content/variants/{id}/media ───────────────────────────────────

class MediaUpdateBody(BaseModel):
    asset_url: str
    asset_type: str = "image"
    asset_source: str = "library"


@router.patch("/variants/{variant_id}/media")
async def update_variant_media(ctx: Ctx, variant_id: str, body: MediaUpdateBody, db: DbSession):
    v = await _get_variant_or_404(variant_id, ctx.business_id, db)
    meta = v.generation_metadata or {}
    meta.update({"asset_url": body.asset_url, "asset_type": body.asset_type, "asset_source": body.asset_source})
    repo = ContentVariantRepository(db)
    v = await repo.update(v, generation_metadata=meta)
    return envelope(_fmt_variant(v), ctx.request_id)
