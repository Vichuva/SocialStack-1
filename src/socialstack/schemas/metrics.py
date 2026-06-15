from pydantic import BaseModel


class MetricsResponse(BaseModel):
    id: str
    publish_event_id: str
    business_id: str
    platform: str
    collected_at: str
    impressions: int | None
    reach: int | None
    likes: int | None
    comments: int | None
    saves: int | None
    shares: int | None
    clicks: int | None
    engagement_rate: float | None

    model_config = {"from_attributes": True}


class CollectMetricsRequest(BaseModel):
    business_id: str | None = None
    idempotency_key: str | None = None
