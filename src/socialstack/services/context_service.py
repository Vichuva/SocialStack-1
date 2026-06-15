import asyncio
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.repositories.business_repo import BusinessPreferencesRepository, BusinessRepository
from socialstack.utils.errors import NotFoundError


@dataclass
class GenerationContext:
    business_id: str
    business_name: str
    industry: str
    brand_tone: str
    pain_points: list[str]
    ai_generate_images: bool
    auto_approve: bool
    tier: str


async def build_context(session: AsyncSession, business_id: str) -> GenerationContext:
    biz_repo = BusinessRepository(session)
    prefs_repo = BusinessPreferencesRepository(session)

    business, prefs = await asyncio.gather(
        biz_repo.get(business_id),
        prefs_repo.get_by_business(business_id),
    )

    if not business:
        raise NotFoundError("Business", business_id)

    return GenerationContext(
        business_id=business_id,
        business_name=business.name,
        industry=business.industry,
        brand_tone=prefs.brand_tone if prefs else "professional",
        pain_points=prefs.pain_points if prefs else [],
        ai_generate_images=prefs.ai_generate_images if prefs else True,
        auto_approve=prefs.auto_approve if prefs else False,
        tier=prefs.tier if prefs else "standard",
    )
