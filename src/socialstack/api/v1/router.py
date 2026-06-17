from fastapi import APIRouter

from socialstack.api.v1 import (
    health, businesses, calendars, slots, generation,
    publishing, metrics, runs, schedule_templates,
    packages, social_dm,
)

api_router = APIRouter(prefix="/v1")

api_router.include_router(health.router)
api_router.include_router(businesses.router, prefix="/businesses")
api_router.include_router(schedule_templates.router, prefix="/businesses")
api_router.include_router(calendars.router, prefix="/calendars")
api_router.include_router(slots.router, prefix="/slots")
api_router.include_router(generation.router, prefix="/generation")
api_router.include_router(publishing.router)
api_router.include_router(metrics.router, prefix="/metrics")
api_router.include_router(runs.router, prefix="/runs")
api_router.include_router(packages.router, prefix="/packages")
api_router.include_router(social_dm.router)
