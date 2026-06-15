from sqlalchemy import select

from socialstack.db.models.media import MediaAsset
from socialstack.repositories.base import BaseRepository


class MediaAssetRepository(BaseRepository[MediaAsset]):
    model = MediaAsset

    async def get_by_variant(self, variant_id: str) -> list[MediaAsset]:
        stmt = select(MediaAsset).where(MediaAsset.variant_id == variant_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
