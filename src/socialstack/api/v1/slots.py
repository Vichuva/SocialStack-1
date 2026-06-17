from fastapi import APIRouter, Query

from socialstack.dependencies import DbSession
from socialstack.repositories.content_repo import ContentSlotRepository
from socialstack.schemas.calendar import SlotCreate, SlotResponse, SlotUpdate

router = APIRouter(tags=["slots"])


@router.get("", response_model=list[SlotResponse])
async def list_slots(
    db: DbSession,
    calendar_id: str | None = Query(None),
    business_id: str | None = Query(None),
    status: str | None = Query(None),
):
    repo = ContentSlotRepository(db)
    if calendar_id:
        slots = await repo.get_by_calendar(calendar_id, status=status)
    elif business_id:
        slots = await repo.list(business_id=business_id, status=status)
    else:
        slots = []
    return [_slot_response(s) for s in slots]


@router.get("/{slot_id}", response_model=SlotResponse)
async def get_slot(slot_id: str, db: DbSession):
    repo = ContentSlotRepository(db)
    slot = await repo.get_or_raise(slot_id)
    return _slot_response(slot)


@router.patch("/{slot_id}", response_model=SlotResponse)
async def update_slot(slot_id: str, body: SlotUpdate, db: DbSession):
    repo = ContentSlotRepository(db)
    slot = await repo.get_or_raise(slot_id)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        slot = await repo.update(slot, **updates)
    return _slot_response(slot)


@router.get("/{slot_id}/content")
async def get_slot_content(slot_id: str, db: DbSession):
    from socialstack.repositories.content_repo import ContentBriefRepository, ContentVariantRepository
    from socialstack.repositories.media_repo import MediaAssetRepository
    slot = await ContentSlotRepository(db).get_or_raise(slot_id)
    brief = await ContentBriefRepository(db).get_latest_for_slot(slot_id)
    variant = await ContentVariantRepository(db).get_latest_for_slot_platform(slot_id, slot.platform)
    # Load all versions for history
    from socialstack.repositories.content_repo import ContentVariantRepository as CVR
    all_variants = await CVR(db).get_all_versions(slot_id, slot.platform)

    # Load media asset for the current variant
    image_url = None
    if variant:
        assets = await MediaAssetRepository(db).get_by_variant(variant.id)
        ai_asset = next((a for a in assets if a.source == "ai_generated" and a.storage_url), None)
        if ai_asset:
            image_url = ai_asset.storage_url

    return {
        "slot_id": slot_id,
        "platform": slot.platform,
        "status": slot.status,
        "brief": {
            "hook": brief.hook,
            "key_message": brief.key_message,
            "emotional_angle": brief.emotional_angle,
            "visual_direction": brief.visual_direction,
            "cta": brief.cta,
        } if brief else None,
        "variant": {
            "id": variant.id,
            "caption": variant.caption,
            "content": variant.content or variant.caption,
            "hashtags": variant.hashtags,
            "char_count": variant.char_count,
            "version": variant.version,
            "review_status": getattr(variant, "review_status", "pending"),
            "is_current": getattr(variant, "is_current", True),
            "regeneration_count": getattr(variant, "regeneration_count", 0),
            "image_url": image_url,
        } if variant else None,
        "all_versions": [
            {
                "id": v.id,
                "version": v.version,
                "caption": v.caption,
                "content": v.content or v.caption,
                "hashtags": v.hashtags,
                "review_status": getattr(v, "review_status", "pending"),
                "is_current": getattr(v, "is_current", False),
                "is_active": getattr(v, "is_active", True),
                "regeneration_count": getattr(v, "regeneration_count", 0),
            }
            for v in all_variants
        ],
    }


def _slot_response(slot) -> SlotResponse:
    return SlotResponse(
        id=slot.id,
        calendar_id=slot.calendar_id,
        calendar_day_id=getattr(slot, "calendar_day_id", None),
        business_id=slot.business_id,
        platform=slot.platform,
        status=slot.status,
        content_type=getattr(slot, "content_type", "text_image"),
        scheduled_at=slot.scheduled_at.isoformat() if slot.scheduled_at else None,
        published_at=slot.published_at.isoformat() if slot.published_at else None,
    )
