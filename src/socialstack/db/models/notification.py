from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialstack.db.base import Base, TimestampMixin, UUIDPrimaryKey


class Notification(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "notifications"

    business_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    # type: approval_required | content_ready | publish_success | publish_failure
    #        token_expiration | workflow_failure
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    # status: pending | sent | failed
    sent_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    channel: Mapped[str] = mapped_column(String(50), default="webhook", nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
