from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from socialstack.db.base import Base, TimestampMixin, UUIDPrimaryKey


class SocialPlatformConnection(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "social_platform_connections"

    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token_enc: Mapped[str] = mapped_column(String(2048), nullable=False)
    # connection_config_enc is the PRD-aligned name for the same field
    connection_config_enc: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    token_expires_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scopes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    business: Mapped["Business"] = relationship("Business", back_populates="social_connections")


from socialstack.db.models.business import Business  # noqa: E402, F401
