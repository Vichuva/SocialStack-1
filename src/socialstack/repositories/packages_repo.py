from sqlalchemy import select
from sqlalchemy.orm import selectinload

from socialstack.db.models.packages import ContentPackage, ContentPackageItem
from socialstack.repositories.base import BaseRepository


class ContentPackageRepository(BaseRepository[ContentPackage]):
    model = ContentPackage

    async def list_active(self) -> list[ContentPackage]:
        stmt = (
            select(ContentPackage)
            .options(selectinload(ContentPackage.items))
            .where(ContentPackage.is_active.is_(True))
            .order_by(ContentPackage.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_items(self, package_id: str) -> ContentPackage | None:
        stmt = (
            select(ContentPackage)
            .options(selectinload(ContentPackage.items))
            .where(ContentPackage.id == package_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
