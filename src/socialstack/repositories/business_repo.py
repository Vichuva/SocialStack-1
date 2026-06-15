from sqlalchemy import select
from sqlalchemy.orm import selectinload

from socialstack.db.models.business import Business, BusinessPreferences
from socialstack.repositories.base import BaseRepository


class BusinessRepository(BaseRepository[Business]):
    model = Business

    async def get_with_preferences(self, business_id: str) -> Business | None:
        stmt = (
            select(Business)
            .options(selectinload(Business.preferences))
            .where(Business.id == business_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class BusinessPreferencesRepository(BaseRepository[BusinessPreferences]):
    model = BusinessPreferences

    async def get_by_business(self, business_id: str) -> BusinessPreferences | None:
        stmt = select(BusinessPreferences).where(BusinessPreferences.business_id == business_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, business_id: str, **kwargs) -> BusinessPreferences:
        existing = await self.get_by_business(business_id)
        if existing:
            return await self.update(existing, **kwargs)
        return await self.create(business_id=business_id, **kwargs)
