import json

import redis.asyncio as aioredis

from socialstack.config import get_settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def check_idempotency(key: str) -> dict | None:
    """Return existing {run_id, status} if key already processed, else None."""
    r = get_redis()
    raw = await r.get(f"idem:{key}")
    if raw:
        return json.loads(raw)
    return None


async def set_idempotency(key: str, run_id: str, status: str, ttl_seconds: int = 86400) -> None:
    r = get_redis()
    await r.set(f"idem:{key}", json.dumps({"run_id": run_id, "status": status}), ex=ttl_seconds)


async def update_idempotency_status(key: str, status: str) -> None:
    r = get_redis()
    raw = await r.get(f"idem:{key}")
    if raw:
        data = json.loads(raw)
        data["status"] = status
        ttl = await r.ttl(f"idem:{key}")
        await r.set(f"idem:{key}", json.dumps(data), ex=max(ttl, 1))


async def acquire_publish_lock(slot_id: str, ttl_seconds: int = 3600) -> bool:
    """SET NX — returns True if lock acquired (slot not already publishing)."""
    r = get_redis()
    result = await r.set(f"publish_lock:{slot_id}", "1", nx=True, ex=ttl_seconds)
    return result is True


async def release_publish_lock(slot_id: str) -> None:
    r = get_redis()
    await r.delete(f"publish_lock:{slot_id}")
