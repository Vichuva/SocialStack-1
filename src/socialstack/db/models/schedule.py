from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from socialstack.db.base import Base, TimestampMixin, UUIDPrimaryKey


class SlotScheduleTemplate(UUIDPrimaryKey, TimestampMixin, Base):
    """Recurring weekly post schedule for a business.

    day_of_week: 0=Monday … 6=Sunday (Python weekday convention)
    post_time:   "HH:MM" 24-hour format
    content_type: text_image | text_only
    """
    __tablename__ = "slot_schedule_templates"

    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    post_time: Mapped[str] = mapped_column(String(5), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), default="text_image", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    business: Mapped["Business"] = relationship("Business", back_populates="slot_templates")


from socialstack.db.models.business import Business  # noqa: E402, F401
