from fastapi import APIRouter, status

from socialstack.dependencies import DbSession
from socialstack.repositories.business_repo import BusinessPreferencesRepository, BusinessRepository
from socialstack.db.models.social import SocialPlatformConnection
from socialstack.schemas.business import (
    BusinessCreate,
    BusinessResponse,
    BusinessUpdate,
    PreferencesResponse,
    PreferencesUpdate,
    SocialConnectionCreate,
    SocialConnectionResponse,
)
from socialstack.utils.encryption import encrypt_token
from socialstack.utils.errors import NotFoundError
from socialstack.config import get_settings

router = APIRouter(tags=["businesses"])


def _prefs_response(prefs, business_id: str) -> PreferencesResponse:
    if not prefs:
        return PreferencesResponse(
            id="",
            business_id=business_id,
            brand_tones=["professional"],
            target_audience=[],
            pain_points=[],
            ai_generate_images=True,
            auto_approve=False,
            tier="standard",
        )
    return PreferencesResponse(
        id=prefs.id,
        business_id=prefs.business_id,
        brand_tones=prefs.brand_tones or ["professional"],
        target_audience=prefs.target_audience or [],
        pain_points=prefs.pain_points or [],
        ai_generate_images=prefs.ai_generate_images,
        auto_approve=prefs.auto_approve,
        tier=prefs.tier,
    )


@router.post("", response_model=BusinessResponse, status_code=status.HTTP_201_CREATED)
async def create_business(body: BusinessCreate, db: DbSession):
    repo = BusinessRepository(db)
    business = await repo.create(**body.model_dump())
    return BusinessResponse(
        id=business.id,
        name=business.name,
        industry=business.industry,
        timezone=business.timezone,
        compliance_tier=business.compliance_tier,
        is_active=business.is_active,
        created_at=business.created_at.isoformat(),
    )


@router.get("/{business_id}", response_model=BusinessResponse)
async def get_business(business_id: str, db: DbSession):
    repo = BusinessRepository(db)
    business = await repo.get_or_raise(business_id)
    return BusinessResponse(
        id=business.id,
        name=business.name,
        industry=business.industry,
        timezone=business.timezone,
        compliance_tier=business.compliance_tier,
        is_active=business.is_active,
        created_at=business.created_at.isoformat(),
    )


@router.patch("/{business_id}", response_model=BusinessResponse)
async def update_business(business_id: str, body: BusinessUpdate, db: DbSession):
    repo = BusinessRepository(db)
    business = await repo.get_or_raise(business_id)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    business = await repo.update(business, **updates)
    return BusinessResponse(
        id=business.id,
        name=business.name,
        industry=business.industry,
        timezone=business.timezone,
        compliance_tier=business.compliance_tier,
        is_active=business.is_active,
        created_at=business.created_at.isoformat(),
    )


@router.put("/{business_id}/preferences", response_model=PreferencesResponse)
async def upsert_preferences(business_id: str, body: PreferencesUpdate, db: DbSession):
    await BusinessRepository(db).get_or_raise(business_id)
    prefs_repo = BusinessPreferencesRepository(db)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    prefs = await prefs_repo.upsert(business_id, **updates)
    return _prefs_response(prefs, business_id)


@router.get("/{business_id}/preferences", response_model=PreferencesResponse)
async def get_preferences(business_id: str, db: DbSession):
    prefs_repo = BusinessPreferencesRepository(db)
    prefs = await prefs_repo.get_by_business(business_id)
    return _prefs_response(prefs, business_id)


@router.post(
    "/{business_id}/social-connections",
    response_model=SocialConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_social_connection(business_id: str, body: SocialConnectionCreate, db: DbSession):
    await BusinessRepository(db).get_or_raise(business_id)

    settings = get_settings()
    encrypted = encrypt_token(body.access_token, settings.token_encryption_key)
    encrypted_refresh = (
        encrypt_token(body.refresh_token, settings.token_encryption_key)
        if body.refresh_token
        else None
    )

    conn = SocialPlatformConnection(
        business_id=business_id,
        platform=body.platform,
        account_name=body.account_name,
        platform_account_id=body.platform_account_id,
        access_token_enc=encrypted,
        refresh_token_enc=encrypted_refresh,
        token_expires_at=body.token_expires_at,
        scopes=body.scopes,
    )
    db.add(conn)
    await db.flush()
    await db.refresh(conn)

    return SocialConnectionResponse(
        id=conn.id,
        business_id=conn.business_id,
        platform=conn.platform,
        account_name=conn.account_name,
        platform_account_id=conn.platform_account_id,
        is_active=conn.is_active,
    )


@router.get("/{business_id}/social-connections", response_model=list[SocialConnectionResponse])
async def list_social_connections(business_id: str, db: DbSession):
    from sqlalchemy import select
    stmt = select(SocialPlatformConnection).where(
        SocialPlatformConnection.business_id == business_id
    )
    result = await db.execute(stmt)
    conns = result.scalars().all()
    return [
        SocialConnectionResponse(
            id=c.id,
            business_id=c.business_id,
            platform=c.platform,
            account_name=c.account_name,
            platform_account_id=c.platform_account_id,
            is_active=c.is_active,
        )
        for c in conns
    ]


@router.delete(
    "/{business_id}/social-connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_social_connection(business_id: str, connection_id: str, db: DbSession):
    from sqlalchemy import select
    stmt = select(SocialPlatformConnection).where(
        SocialPlatformConnection.id == connection_id,
        SocialPlatformConnection.business_id == business_id,
    )
    result = await db.execute(stmt)
    conn = result.scalar_one_or_none()
    if not conn:
        raise NotFoundError("SocialPlatformConnection", connection_id)
    await db.delete(conn)
    await db.flush()
