from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from socialstack.config import get_settings
from socialstack.middleware.logging import LoggingMiddleware
from socialstack.utils.errors import NotFoundError, SocialStackError, ValidationError
from socialstack.utils.logging import setup_logging


def _init_sentry(dsn: str) -> None:
    if not dsn:
        return
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=dsn, traces_sample_rate=0.1)
    except ImportError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_format)
    _init_sentry(settings.sentry_dsn)
    if settings.storage_backend == "local":
        import os
        os.makedirs(settings.local_storage_path, exist_ok=True)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="SocialStack API",
        description="Social media content automation platform",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(LoggingMiddleware)
    origins = (
        [settings.frontend_url]
        if settings.frontend_url and settings.frontend_url != "*"
        else ["*"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(SocialStackError)
    async def socialstack_error_handler(request: Request, exc: SocialStackError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"code": exc.code, "message": exc.message, "status": 500},
        )

    # Legacy v1 router (keeps existing integrations working)
    from socialstack.api.v1.router import api_router
    app.include_router(api_router)

    # SuperOne-compatible router at /api/v1/content/* and /api/v1/social/*
    from socialstack.api.superone.router import superone_router
    app.include_router(superone_router)

    # Serve local media files in dev
    if settings.storage_backend == "local":
        from fastapi.staticfiles import StaticFiles
        import os
        os.makedirs(settings.local_storage_path, exist_ok=True)
        app.mount("/media", StaticFiles(directory=settings.local_storage_path), name="media")

    return app
