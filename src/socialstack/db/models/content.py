from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from socialstack.db.base import Base, TimestampMixin, UUIDPrimaryKey


class ContentSlot(UUIDPrimaryKey, TimestampMixin, Base):
    """One slot = one post for one platform on one calendar day."""
    __tablename__ = "content_slots"

    calendar_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False
    )
    calendar_day_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("calendar_days.id", ondelete="SET NULL"), nullable=True
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    # Status flow: draft/empty → pending_brief → pending_caption → pending_review → approved → published | failed
    content_type: Mapped[str] = mapped_column(String(50), default="text_image", nullable=False)
    # content_type: text_image | text_only
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Theme / content fields (slot-centric API)
    theme: Mapped[str | None] = mapped_column(String(500), nullable=True)
    objective: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # PRD alignment fields
    problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    package_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    calendar: Mapped["Calendar"] = relationship("Calendar", back_populates="slots")
    calendar_day: Mapped["CalendarDay | None"] = relationship("CalendarDay", back_populates="slots")
    briefs: Mapped[list["ContentBrief"]] = relationship("ContentBrief", back_populates="slot")
    variants: Mapped[list["ContentVariant"]] = relationship("ContentVariant", back_populates="slot")
    publish_events: Mapped[list["PublishEvent"]] = relationship("PublishEvent", back_populates="slot")
    feedback: Mapped[list["ContentFeedback"]] = relationship("ContentFeedback", back_populates="slot")


class ContentBrief(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "content_briefs"

    slot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("content_slots.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    key_message: Mapped[str] = mapped_column(Text, nullable=False)
    emotional_angle: Mapped[str] = mapped_column(Text, nullable=False)
    visual_direction: Mapped[str] = mapped_column(Text, nullable=False)
    cta: Mapped[str] = mapped_column(Text, nullable=False)

    slot: Mapped["ContentSlot"] = relationship("ContentSlot", back_populates="briefs")
    variants: Mapped[list["ContentVariant"]] = relationship("ContentVariant", back_populates="brief")


class ContentVariant(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "content_variants"

    slot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("content_slots.id", ondelete="CASCADE"), nullable=False
    )
    brief_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("content_briefs.id", ondelete="SET NULL"), nullable=True
    )
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    # content mirrors caption — the PRD-aligned field name
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    variant_type: Mapped[str] = mapped_column(String(50), default="standard", nullable=False)
    # variant_type: standard | emotional | educational | promotional | question | social_proof
    # PRD alignment fields
    review_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    # review_status: pending | approved | rejected
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    regeneration_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    platform_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generation_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    slot: Mapped["ContentSlot"] = relationship("ContentSlot", back_populates="variants")
    brief: Mapped["ContentBrief | None"] = relationship("ContentBrief", back_populates="variants")
    media_assets: Mapped[list["MediaAsset"]] = relationship("MediaAsset", back_populates="variant")
    publish_events: Mapped[list["PublishEvent"]] = relationship("PublishEvent", back_populates="variant")


class ContentFeedback(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "content_feedback"

    slot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("content_slots.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("content_variants.id", ondelete="SET NULL"), nullable=True
    )
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)

    slot: Mapped["ContentSlot"] = relationship("ContentSlot", back_populates="feedback")


from socialstack.db.models.calendar import Calendar, CalendarDay  # noqa: E402, F401
from socialstack.db.models.media import MediaAsset  # noqa: E402, F401
from socialstack.db.models.publish import PublishEvent  # noqa: E402, F401
