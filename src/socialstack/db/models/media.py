from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from socialstack.db.base import Base, TimestampMixin, UUIDPrimaryKey


class MediaAsset(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "media_assets"

    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    variant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("content_variants.id", ondelete="SET NULL"), nullable=True
    )
    storage_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), default="image", nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), default="image/png", nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="ai_generated", nullable=False)
    # source: ai_generated | library | uploaded
    ai_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)

    variant: Mapped["ContentVariant | None"] = relationship("ContentVariant", back_populates="media_assets")


from socialstack.db.models.content import ContentVariant  # noqa: E402, F401
