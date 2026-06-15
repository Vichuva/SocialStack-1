from pydantic import BaseModel, Field


class SlotTemplateCreate(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday … 6=Sunday")
    post_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM 24-hour")
    content_type: str = Field("text_image", pattern=r"^(text_image|text_only)$")


class SlotTemplateResponse(BaseModel):
    id: str
    business_id: str
    day_of_week: int
    post_time: str
    content_type: str
    is_active: bool

    model_config = {"from_attributes": True}
