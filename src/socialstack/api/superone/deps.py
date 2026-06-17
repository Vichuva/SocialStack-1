"""
Auth dependency for the SuperOne-compatible API.

SuperOne issues custom JWTs (injected via Supabase Auth Hook) with these claims:
  {
    "sub": "user-uuid",
    "business_id": "biz-uuid",
    "user_role": "manager",
    "tier": "tier_s",
    "plan_id": null,
    "aud": "authenticated",
    "exp": 1234567890
  }

Algorithm auto-detection from JWT header:
  - HS256 → verify with SUPABASE_JWT_SECRET
  - ES256 → fetch public key from {SUPABASE_URL}/auth/v1/.well-known/jwks.json (cached 1 h)

Internal calls (n8n / agents, no user JWT):
  X-API-Key: <BACKEND_API_KEY>  +  X-Business-Id: <uuid>
"""
import base64
import json
import time
import uuid
from dataclasses import dataclass

import httpx
from fastapi import Header, HTTPException, status

from socialstack.config import get_settings
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# JWKS cache (module-level, shared across all requests)
# ---------------------------------------------------------------------------
_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL_SECONDS = 3600


# ---------------------------------------------------------------------------
# Request context
# ---------------------------------------------------------------------------

@dataclass
class RequestContext:
    user_id: str
    business_id: str
    user_role: str
    tier: str
    request_id: str


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _decode_unverified_header(token: str) -> dict:
    try:
        header_b64 = token.split(".")[0]
        padding = "=" * (-len(header_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(header_b64 + padding))
    except Exception:
        return {}


def _decode_unverified_payload(token: str) -> dict:
    try:
        payload_b64 = token.split(".")[1]
        padding = "=" * (-len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
    except Exception:
        return {}


async def _fetch_jwks(supabase_url: str) -> list[dict]:
    """Async-fetch JWKS keys from Supabase, respecting 1-hour cache."""
    now = time.monotonic()
    if _jwks_cache["keys"] and now - _jwks_cache["fetched_at"] < _JWKS_TTL_SECONDS:
        return _jwks_cache["keys"]

    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.error("jwks_fetch_failed", url=jwks_url, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "jwks_unavailable", "message": "Could not fetch JWKS keys", "status": 503},
        )

    keys = data.get("keys", [])
    _jwks_cache["keys"] = keys
    _jwks_cache["fetched_at"] = now
    return keys


async def _verify_token(token: str, settings) -> dict:
    """Verify JWT, auto-detecting HS256 vs ES256. Returns the decoded payload."""
    from jose import JWTError, jwt, jwk

    header = _decode_unverified_header(token)
    alg = header.get("alg", "HS256")

    try:
        if alg == "ES256":
            if not settings.supabase_url:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"code": "config_error", "message": "SUPABASE_URL is not set", "status": 500},
                )
            keys = await _fetch_jwks(settings.supabase_url)
            kid = header.get("kid")

            # Find matching key by kid, or try all keys
            candidates = [k for k in keys if not kid or k.get("kid") == kid]
            if not candidates:
                candidates = keys

            last_error: Exception | None = None
            for key_data in candidates:
                try:
                    public_key = jwk.construct(key_data, algorithm="ES256")
                    payload = jwt.decode(
                        token,
                        public_key,
                        algorithms=["ES256"],
                        options={"verify_aud": False},
                    )
                    return payload
                except JWTError as exc:
                    last_error = exc
                    continue

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "invalid_token", "message": str(last_error or "ES256 verification failed"), "status": 401},
            )

        else:  # HS256
            secret = settings.supabase_jwt_secret
            if not secret:
                # Dev fallback: skip verification, trust the token structurally
                logger.warning("jwt_no_secret_dev_mode")
                return _decode_unverified_payload(token)

            return jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )

    except HTTPException:
        raise
    except Exception as exc:
        err_str = str(exc).lower()
        if "expired" in err_str:
            code, msg = "token_expired", "Token has expired"
        elif "signature" in err_str:
            code, msg = "invalid_signature", "Invalid token signature"
        else:
            code, msg = "invalid_token", str(exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": code, "message": msg, "status": 401},
        )


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_context(
    authorization: str | None = Header(None),
    x_business_id: str | None = Header(None, alias="X-Business-Id"),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> RequestContext:
    settings = get_settings()
    rid = str(uuid.uuid4())

    # ── Mode 1: SuperOne JWT (Bearer token) ──────────────────────────────────
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        payload = await _verify_token(token, settings)

        business_id = payload.get("business_id")
        if not business_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "missing_business_id", "message": "JWT has no business_id claim", "status": 401},
            )

        return RequestContext(
            user_id=payload.get("sub", ""),
            business_id=business_id,
            user_role=payload.get("user_role", ""),
            tier=payload.get("tier", ""),
            request_id=rid,
        )

    # ── Mode 2: Internal API key (n8n / agents) ───────────────────────────────
    if x_api_key:
        if not settings.backend_api_key or x_api_key != settings.backend_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "invalid_api_key", "message": "Invalid API key", "status": 401},
            )
        if not x_business_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "missing_business_id", "message": "X-Business-Id header required with API key auth", "status": 401},
            )
        return RequestContext(
            user_id="system",
            business_id=x_business_id,
            user_role="system",
            tier="",
            request_id=rid,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "auth_required", "message": "Authorization: Bearer <token> is required", "status": 401},
    )


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def envelope(data, request_id: str = "") -> dict:
    return {"data": data, "meta": {"request_id": request_id or str(uuid.uuid4())}}


def paginated(data: list, total: int, has_more: bool, next_cursor=None) -> dict:
    return {
        "data": data,
        "pagination": {"total": total, "has_more": has_more, "next_cursor": next_cursor},
    }
