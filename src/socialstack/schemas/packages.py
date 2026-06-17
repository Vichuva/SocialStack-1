from pydantic import BaseModel


class ContentPackageItemResponse(BaseModel):
    id: str
    package_id: str
    content_types: list[str]
    max_posts: int
    period: str

    model_config = {"from_attributes": True}


class ContentPackageResponse(BaseModel):
    id: str
    name: str
    billing_cycle: str
    posts_per_week: int
    content_types: list[str]
    is_active: bool
    items: list[ContentPackageItemResponse] = []

    model_config = {"from_attributes": True}
