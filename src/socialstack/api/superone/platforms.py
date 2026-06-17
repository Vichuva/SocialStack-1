from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, select

from socialstack.api.superone.deps import RequestContext, envelope, get_context
from socialstack.config import get_settings
from socialstack.db.models.social import SocialPlatformConnection
from socialstack.dependencies import DbSession
from socialstack.utils.encryption import encrypt_token

router = APIRouter(tags=["platforms"])
Ctx = Annotated[RequestContext, Depends(get_context)]

ALLOWED_PLATFORMS = {
    "instagram", "facebook", "linkedin", "twitter",
    "tiktok", "youtube_shorts", "threads",
}


class PlatformConnectBody(BaseModel):
    platform: str
    access_token: str = "placeholder"
    refresh_token: str | None = None
    account_id: str
    account_name: str


def _fmt(conn) -> dict:
    return {
        "id": conn.id,
        "platform": conn.platform,
        "platform_account_id": conn.platform_account_id,
        "account_name": conn.account_name,
        "is_active": conn.is_active,
        "last_verified_at": getattr(conn, "last_verified_at", None),
    }


@router.get("/platforms")
async def list_platforms(ctx: Ctx, db: DbSession):
    stmt = select(SocialPlatformConnection).where(
        and_(
            SocialPlatformConnection.business_id == ctx.business_id,
            SocialPlatformConnection.is_active.is_(True),
        )
    )
    result = await db.execute(stmt)
    conns = result.scalars().all()
    return envelope([_fmt(c) for c in conns], ctx.request_id)


@router.post("/platforms/connect", status_code=status.HTTP_201_CREATED)
async def connect_platform(ctx: Ctx, body: PlatformConnectBody, db: DbSession):
    if body.platform not in ALLOWED_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_platform", "message": f"Platform must be one of {sorted(ALLOWED_PLATFORMS)}", "status": 400},
        )

    settings = get_settings()
    encrypted = encrypt_token(body.access_token, settings.token_encryption_key) if settings.token_encryption_key else body.access_token
    encrypted_refresh = (
        encrypt_token(body.refresh_token, settings.token_encryption_key)
        if body.refresh_token and settings.token_encryption_key
        else body.refresh_token
    )

    # Upsert: update if same business+platform+account_id exists
    stmt = select(SocialPlatformConnection).where(
        and_(
            SocialPlatformConnection.business_id == ctx.business_id,
            SocialPlatformConnection.platform == body.platform,
            SocialPlatformConnection.platform_account_id == body.account_id,
        )
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.is_active = True
        existing.access_token_enc = encrypted
        existing.account_name = body.account_name
        await db.flush()
        await db.refresh(existing)
    else:
        existing = SocialPlatformConnection(
            business_id=ctx.business_id,
            platform=body.platform,
            platform_account_id=body.account_id,
            account_name=body.account_name,
            access_token_enc=encrypted,
            refresh_token_enc=encrypted_refresh,
        )
        db.add(existing)
        await db.flush()
        await db.refresh(existing)

    return envelope({"connected": True, "platform": body.platform}, ctx.request_id)


@router.delete("/platforms/{platform_connection_id}")
async def disconnect_platform(ctx: Ctx, platform_connection_id: str, db: DbSession):
    stmt = select(SocialPlatformConnection).where(
        and_(
            SocialPlatformConnection.id == platform_connection_id,
            SocialPlatformConnection.business_id == ctx.business_id,
        )
    )
    result = await db.execute(stmt)
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Platform connection not found", "status": 404},
        )
    conn.is_active = False
    await db.flush()
    return envelope({"disconnected": True}, ctx.request_id)
