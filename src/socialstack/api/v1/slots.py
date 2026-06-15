from fastapi import APIRouter, Query, status

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


def _slot_response(slot) -> SlotResponse:
    return SlotResponse(
        id=slot.id,
        calendar_id=slot.calendar_id,
        business_id=slot.business_id,
        platform=slot.platform,
        status=slot.status,
        scheduled_at=slot.scheduled_at.isoformat() if slot.scheduled_at else None,
        published_at=slot.published_at.isoformat() if slot.published_at else None,
    )
