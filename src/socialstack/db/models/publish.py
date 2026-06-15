from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from socialstack.db.base import Base, TimestampMixin, UUIDPrimaryKey


class PublishEvent(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "publish_events"

    slot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("content_slots.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("content_variants.id", ondelete="SET NULL"), nullable=True
    )
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    platform_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    permalink: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)
    # status: success | failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_method: Mapped[str | None] = mapped_column(String(100), nullable=True)

    slot: Mapped["ContentSlot"] = relationship("ContentSlot", back_populates="publish_events")
    variant: Mapped["ContentVariant | None"] = relationship("ContentVariant", back_populates="publish_events")
    metrics: Mapped[list["PostMetrics"]] = relationship("PostMetrics", back_populates="publish_event")


from socialstack.db.models.content import ContentSlot, ContentVariant  # noqa: E402, F401
from socialstack.db.models.metrics import PostMetrics  # noqa: E402, F401
