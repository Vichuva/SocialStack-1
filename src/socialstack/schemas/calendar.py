from pydantic import BaseModel, Field

from socialstack.schemas.common import ObjectiveType, Platform


class CalendarCreate(BaseModel):
    business_id: str
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2024, le=2100)


class CalendarDayResponse(BaseModel):
    id: str
    date: str
    day_number: int
    theme: str | None
    objective: str | None
    post_idea: str | None

    model_config = {"from_attributes": True}


class SlotStatusCounts(BaseModel):
    draft: int = 0
    pending_brief: int = 0
    pending_caption: int = 0
    pending_review: int = 0
    approved: int = 0
    published: int = 0
    failed: int = 0


class CalendarResponse(BaseModel):
    id: str
    business_id: str
    month: int
    year: int
    status: str
    days: list[CalendarDayResponse] = []
    slot_counts: SlotStatusCounts = SlotStatusCounts()

    model_config = {"from_attributes": True}


class GenerateThemesRequest(BaseModel):
    idempotency_key: str | None = None


class GenerateThemesResponse(BaseModel):
    run_id: str
    status: str = "queued"
    calendar_id: str


class SlotCreate(BaseModel):
    calendar_id: str
    calendar_day_id: str | None = None
    business_id: str
    platform: Platform
    content_type: str = Field("text_image", pattern=r"^(text_image|text_only)$")
    scheduled_at: str | None = None


class SlotUpdate(BaseModel):
    status: str | None = None
    scheduled_at: str | None = None


class SlotResponse(BaseModel):
    id: str
    calendar_id: str
    business_id: str
    platform: str
    status: str
    content_type: str
    scheduled_at: str | None
    published_at: str | None

    model_config = {"from_attributes": True}
