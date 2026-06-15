from fastapi import APIRouter, status

from socialstack.dependencies import DbSession
from socialstack.repositories.business_repo import BusinessRepository
from socialstack.repositories.schedule_repo import SlotScheduleTemplateRepository
from socialstack.schemas.schedule import SlotTemplateCreate, SlotTemplateResponse
from socialstack.utils.errors import NotFoundError

router = APIRouter(tags=["schedule-templates"])


@router.get("/{business_id}/slot-templates", response_model=list[SlotTemplateResponse])
async def list_slot_templates(business_id: str, db: DbSession):
    await BusinessRepository(db).get_or_raise(business_id)
    repo = SlotScheduleTemplateRepository(db)
    templates = await repo.list_for_business(business_id, active_only=False)
    return [SlotTemplateResponse.model_validate(t) for t in templates]


@router.post(
    "/{business_id}/slot-templates",
    response_model=SlotTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_slot_template(business_id: str, body: SlotTemplateCreate, db: DbSession):
    await BusinessRepository(db).get_or_raise(business_id)
    repo = SlotScheduleTemplateRepository(db)
    template = await repo.create(
        business_id=business_id,
        day_of_week=body.day_of_week,
        post_time=body.post_time,
        content_type=body.content_type,
    )
    return SlotTemplateResponse.model_validate(template)


@router.delete("/{business_id}/slot-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_slot_template(business_id: str, template_id: str, db: DbSession):
    repo = SlotScheduleTemplateRepository(db)
    template = await repo.get(template_id)
    if not template or template.business_id != business_id:
        raise NotFoundError("SlotScheduleTemplate", template_id)
    await db.delete(template)
    await db.flush()
