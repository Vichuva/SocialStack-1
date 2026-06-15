from pydantic import BaseModel

from socialstack.schemas.common import Platform


class PublishRequest(BaseModel):
    idempotency_key: str | None = None


class PublishEventResponse(BaseModel):
    id: str
    slot_id: str
    business_id: str
    platform: str
    platform_post_id: str | None
    permalink: str | None
    status: str
    published_at: str | None

    model_config = {"from_attributes": True}


class ReviewRejectRequest(BaseModel):
    feedback: str
    platform: Platform | None = None
    regenerate: bool = True
    variant_id: str | None = None
