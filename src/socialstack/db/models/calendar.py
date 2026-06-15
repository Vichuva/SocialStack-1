from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from socialstack.db.base import Base, TimestampMixin, UUIDPrimaryKey


class Calendar(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "calendars"

    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)

    business: Mapped["Business"] = relationship("Business", back_populates="calendars")
    days: Mapped[list["CalendarDay"]] = relationship(
        "CalendarDay", back_populates="calendar", order_by="CalendarDay.day_number"
    )
    slots: Mapped[list["ContentSlot"]] = relationship("ContentSlot", back_populates="calendar")


class CalendarDay(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "calendar_days"

    calendar_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    theme: Mapped[str | None] = mapped_column(String(500), nullable=True)
    objective: Mapped[str | None] = mapped_column(String(50), nullable=True)
    post_idea: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    calendar: Mapped["Calendar"] = relationship("Calendar", back_populates="days")
    slots: Mapped[list["ContentSlot"]] = relationship("ContentSlot", back_populates="calendar_day")


from socialstack.db.models.business import Business  # noqa: E402, F401
from socialstack.db.models.content import ContentSlot  # noqa: E402, F401
