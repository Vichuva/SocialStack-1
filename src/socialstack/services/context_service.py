import asyncio
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.repositories.business_repo import BusinessPreferencesRepository, BusinessRepository
from socialstack.utils.errors import NotFoundError


@dataclass
class GenerationContext:
    business_id: str
    business_name: str
    industry: str
    brand_tones: list[str]
    target_audience: list[str]
    pain_points: list[str]
    ai_generate_images: bool
    auto_approve: bool
    tier: str

    @property
    def brand_tone_str(self) -> str:
        """Comma-joined tones for AI prompts."""
        return ", ".join(self.brand_tones) if self.brand_tones else "professional"


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
        brand_tones=prefs.brand_tones if prefs else ["professional"],
        target_audience=prefs.target_audience if prefs else [],
        pain_points=prefs.pain_points if prefs else [],
        ai_generate_images=prefs.ai_generate_images if prefs else True,
        auto_approve=prefs.auto_approve if prefs else False,
        tier=prefs.tier if prefs else "standard",
    )
