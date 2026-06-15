from pydantic import BaseModel, Field


class BusinessCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=100)
    timezone: str = Field("UTC", max_length=50)
    compliance_tier: str = Field("standard", max_length=50)


class BusinessUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    timezone: str | None = None
    compliance_tier: str | None = None


class BusinessResponse(BaseModel):
    id: str
    name: str
    industry: str
    timezone: str
    compliance_tier: str
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


class PreferencesUpdate(BaseModel):
    brand_tones: list[str] | None = None
    target_audience: list[str] | None = None
    pain_points: list[str] | None = None
    ai_generate_images: bool | None = None
    auto_approve: bool | None = None
    tier: str | None = None


class PreferencesResponse(BaseModel):
    id: str
    business_id: str
    brand_tones: list[str]
    target_audience: list[str]
    pain_points: list[str]
    ai_generate_images: bool
    auto_approve: bool
    tier: str

    model_config = {"from_attributes": True}


class SocialConnectionCreate(BaseModel):
    platform: str = Field(..., max_length=50)
    account_name: str = Field(..., max_length=255)
    platform_account_id: str = Field(..., max_length=255)
    access_token: str = Field(..., description="Raw token — will be encrypted at rest")
    refresh_token: str | None = None
    token_expires_at: str | None = None
    scopes: str | None = None


class SocialConnectionResponse(BaseModel):
    id: str
    business_id: str
    platform: str
    account_name: str
    platform_account_id: str
    is_active: bool

    model_config = {"from_attributes": True}
