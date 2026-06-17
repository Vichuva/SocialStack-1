from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from socialstack.api.superone.deps import RequestContext, envelope, get_context
from socialstack.dependencies import DbSession
from socialstack.repositories.business_repo import BusinessPreferencesRepository

router = APIRouter(tags=["preferences"])
Ctx = Annotated[RequestContext, Depends(get_context)]


class PreferencesUpdateBody(BaseModel):
    brand_tone: str | None = None
    pain_points: list[str] | None = None
    target_audience: str | None = None
    auto_approve: bool | None = None
    automation_enabled: bool | None = None
    package_id: str | None = None
    posting_schedule: list[dict] | None = None


def _fmt(prefs) -> dict:
    if not prefs:
        return {}
    return {
        "id": prefs.id,
        "business_id": prefs.business_id,
        "brand_tone": (prefs.brand_tones or ["professional"])[0] if prefs.brand_tones else "professional",
        "pain_points": prefs.pain_points or [],
        "target_audience": (
            prefs.target_audience[0]
            if isinstance(prefs.target_audience, list) and prefs.target_audience
            else (prefs.target_audience or "")
        ),
        "auto_approve": prefs.auto_approve,
        "automation_enabled": getattr(prefs, "automation_enabled", True),
        "package_id": getattr(prefs, "package_id", None),
        "posting_schedule": getattr(prefs, "posting_schedule", None) or [],
    }


@router.get("/preferences")
async def get_preferences(ctx: Ctx, db: DbSession):
    repo = BusinessPreferencesRepository(db)
    prefs = await repo.get_by_business(ctx.business_id)
    return envelope(_fmt(prefs), ctx.request_id)


@router.put("/preferences")
async def upsert_preferences(ctx: Ctx, body: PreferencesUpdateBody, db: DbSession):
    repo = BusinessPreferencesRepository(db)

    updates: dict = {}
    if body.brand_tone is not None:
        updates["brand_tones"] = [body.brand_tone]
    if body.pain_points is not None:
        updates["pain_points"] = body.pain_points
    if body.target_audience is not None:
        updates["target_audience"] = [body.target_audience]
    if body.auto_approve is not None:
        updates["auto_approve"] = body.auto_approve
    if body.package_id is not None:
        updates["package_id"] = body.package_id
    if body.posting_schedule is not None:
        updates["posting_schedule"] = body.posting_schedule

    prefs = await repo.upsert(ctx.business_id, **updates)
    return envelope(_fmt(prefs), ctx.request_id)
