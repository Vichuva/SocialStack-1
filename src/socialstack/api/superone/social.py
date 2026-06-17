import hashlib
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel

from socialstack.api.superone.deps import RequestContext, envelope, paginated, get_context
from socialstack.config import get_settings
from socialstack.dependencies import DbSession
from socialstack.services.social_dm_service import SocialDmService
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["social"])
Ctx = Annotated[RequestContext, Depends(get_context)]


async def _verify_hmac(request: Request) -> bool:
    settings = get_settings()
    secret = settings.social_webhook_secret or settings.inbound_hmac_secret
    if not secret:
        return True
    sig = (
        request.headers.get("X-Hub-Signature-256")
        or request.headers.get("X-Signature")
        or ""
    )
    body = await request.body()
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


# ── 7.1 POST /social/webhooks/inbound — public, no auth ──────────────────────

class InboundPayload(BaseModel):
    platform: str
    sender_id: str
    sender_name: str | None = None
    text: str
    timestamp: str | None = None


@router.post("/social/webhooks/inbound", status_code=status.HTTP_200_OK)
async def inbound_webhook(request: Request, payload: InboundPayload, db: DbSession):
    if not await _verify_hmac(request):
        logger.warning("inbound_webhook_bad_signature", platform=payload.platform)
    svc = SocialDmService(db)
    await svc.receive_inbound(
        platform=payload.platform,
        sender_id=payload.sender_id,
        sender_name=payload.sender_name,
        text=payload.text,
        timestamp=payload.timestamp,
    )
    return {"received": True}


# ── 7.2 GET /social/conversations ────────────────────────────────────────────

@router.get("/social/conversations")
async def list_conversations(
    ctx: Ctx,
    db: DbSession,
    platform: str | None = Query(None),
    conv_status: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
):
    svc = SocialDmService(db)
    convs = await svc.list_conversations(
        business_id=ctx.business_id,
        platform=platform,
        status=conv_status,
        limit=limit,
    )
    return paginated(convs, total=len(convs), has_more=False)


# ── 7.3 GET /social/conversations/{id}/messages ───────────────────────────────

@router.get("/social/conversations/{conversation_id}/messages")
async def get_messages(
    ctx: Ctx,
    conversation_id: str,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None),
):
    svc = SocialDmService(db)
    messages = await svc.get_messages(conversation_id)
    return paginated(messages, total=len(messages), has_more=False)


# ── 7.4 POST /social/conversations/{id}/reply ────────────────────────────────

class ReplyBody(BaseModel):
    content: str
    media_url: str | None = None


@router.post("/social/conversations/{conversation_id}/reply")
async def reply(ctx: Ctx, conversation_id: str, body: ReplyBody, db: DbSession):
    svc = SocialDmService(db)
    result = await svc.reply(conversation_id=conversation_id, content=body.content)
    return envelope(result, ctx.request_id)
