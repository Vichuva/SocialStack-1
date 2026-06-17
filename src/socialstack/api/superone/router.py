from fastapi import APIRouter

from socialstack.api.superone import (
    preferences,
    packages,
    platforms,
    slots,
    variants,
    social,
)

superone_router = APIRouter(prefix="/api/v1")

# /api/v1/content/*
content_router = APIRouter(prefix="/content")
content_router.include_router(preferences.router)
content_router.include_router(packages.router)
content_router.include_router(platforms.router)
content_router.include_router(slots.router)
content_router.include_router(variants.router)

superone_router.include_router(content_router)
superone_router.include_router(social.router)
