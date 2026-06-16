from pydantic import BaseModel, Field

from socialstack.schemas.common import Platform


class BriefData(BaseModel):
    hook: str
    key_message: str
    emotional_angle: str
    visual_direction: str
    cta: str


class OrchestrateRequest(BaseModel):
    calendar_id: str
    business_id: str
    platforms: list[Platform] = Field(default_factory=lambda: [Platform.INSTAGRAM])
    generate_images: bool = False
    calendar_day_id: str | None = None  # if set, generate only for this day
    idempotency_key: str | None = None


class BriefRequest(BaseModel):
    slot_id: str
    business_id: str
    day: dict  # {date, theme, objective, post_idea}
    idempotency_key: str | None = None


class CaptionRequest(BaseModel):
    slot_id: str
    business_id: str
    platform: Platform
    brief: BriefData
    idempotency_key: str | None = None


class AssetRequest(BaseModel):
    slot_id: str
    business_id: str
    platform: Platform
    theme: str
    brief: BriefData
    idempotency_key: str | None = None


class MultiVariantRequest(BaseModel):
    slot_id: str
    business_id: str
    platform: Platform
    brief: BriefData
    variant_count: int = Field(default=3, ge=1, le=5)
    idempotency_key: str | None = None


class RegenerateRequest(BaseModel):
    slot_id: str
    business_id: str
    platform: Platform
    feedback: str = Field(..., min_length=1)
    original_brief: BriefData
    idempotency_key: str | None = None


class TaskResponse(BaseModel):
    run_id: str
    status: str = "queued"


class RunResponse(BaseModel):
    id: str
    workflow: str
    business_id: str | None
    status: str
    started_at: str | None
    finished_at: str | None
    output: dict | None
    error: dict | None

    model_config = {"from_attributes": True}
