import importlib.metadata
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])

_start_time = time.time()


@router.get("/health")
async def liveness():
    return {"status": "ok"}


@router.get("/ready")
async def readiness():
    checks: dict[str, str] = {}
    all_ok = True

    # Check Redis
    try:
        from socialstack.utils.idempotency import get_redis
        r = get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        all_ok = False

    # Check DB
    try:
        from socialstack.db.session import get_sessionmaker
        from sqlalchemy import text
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        all_ok = False

    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
    )


@router.get("/version")
async def version():
    try:
        ver = importlib.metadata.version("socialstack")
    except importlib.metadata.PackageNotFoundError:
        ver = "dev"
    return {
        "version": ver,
        "uptime_seconds": round(time.time() - _start_time),
    }
