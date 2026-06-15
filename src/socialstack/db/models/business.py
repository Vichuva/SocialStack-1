from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from socialstack.db.base import Base, TimestampMixin, UUIDPrimaryKey


class Business(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    compliance_tier: Mapped[str] = mapped_column(String(50), default="standard", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    preferences: Mapped["BusinessPreferences | None"] = relationship(
        "BusinessPreferences", back_populates="business", uselist=False
    )
    social_connections: Mapped[list["SocialPlatformConnection"]] = relationship(
        "SocialPlatformConnection", back_populates="business"
    )
    calendars: Mapped[list["Calendar"]] = relationship("Calendar", back_populates="business")


class BusinessPreferences(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "business_preferences"

    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    brand_tone: Mapped[str] = mapped_column(String(500), default="professional", nullable=False)
    pain_points: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    ai_generate_images: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tier: Mapped[str] = mapped_column(String(50), default="standard", nullable=False)

    business: Mapped["Business"] = relationship("Business", back_populates="preferences")


# Import guard — avoid circular at module level
from socialstack.db.models.social import SocialPlatformConnection  # noqa: E402, F401
from socialstack.db.models.calendar import Calendar  # noqa: E402, F401
