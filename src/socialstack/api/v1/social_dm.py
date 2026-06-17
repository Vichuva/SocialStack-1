import hashlib
import hmac

from fastapi import APIRouter, Query, Request, status
from pydantic import BaseModel

from socialstack.dependencies import DbSession
from socialstack.services.social_dm_service import SocialDmService
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["social_dm"])


class InboundWebhookPayload(BaseModel):
    platform: str
    sender_id: str
    sender_name: str | None = None
    text: str
    timestamp: str | None = None


class ReplyRequest(BaseModel):
    content: str


async def _verify_signature(request: Request) -> bool:
    """Constant-time HMAC-SHA256 verification for inbound webhook."""
    from socialstack.config import get_settings
    settings = get_settings()
    secret = getattr(settings, "inbound_hmac_secret", None)
    if not secret:
        return True  # No secret configured → accept all (dev mode)
    sig_header = (
        request.headers.get("X-Hub-Signature-256")
        or request.headers.get("X-Signature")
        or ""
    )
    body = await request.body()
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig_header, expected)


@router.post("/social/webhooks/inbound", status_code=status.HTTP_200_OK)
async def inbound_webhook(request: Request, payload: InboundWebhookPayload, db: DbSession):
    """Public endpoint — receives inbound social DMs. Verifies HMAC if secret is configured."""
    if not await _verify_signature(request):
        logger.warning("inbound_webhook_bad_signature", platform=payload.platform)
        # Return 200 anyway — never error to the sender
        return {"received": True}

    svc = SocialDmService(db)
    return await svc.receive_inbound(
        platform=payload.platform,
        sender_id=payload.sender_id,
        sender_name=payload.sender_name,
        text=payload.text,
        timestamp=payload.timestamp,
    )


@router.get("/social/conversations")
async def list_conversations(
    db: DbSession,
    business_id: str = Query(...),
    platform: str | None = Query(None),
    conv_status: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
):
    svc = SocialDmService(db)
    convs = await svc.list_conversations(
        business_id=business_id,
        platform=platform,
        status=conv_status,
        limit=limit,
    )
    return {"data": convs}


@router.get("/social/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, db: DbSession):
    svc = SocialDmService(db)
    messages = await svc.get_messages(conversation_id)
    return {"data": messages}


@router.post("/social/conversations/{conversation_id}/reply")
async def reply_to_conversation(conversation_id: str, body: ReplyRequest, db: DbSession):
    svc = SocialDmService(db)
    return await svc.reply(conversation_id=conversation_id, content=body.content)
