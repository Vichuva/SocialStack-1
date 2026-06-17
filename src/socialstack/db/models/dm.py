from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from socialstack.db.base import Base, UUIDPrimaryKey


class SocialConversation(UUIDPrimaryKey, Base):
    """One conversation thread per (business, platform, sender)."""
    __tablename__ = "social_conversations"
    __table_args__ = (
        UniqueConstraint("business_id", "platform", "sender_id", name="uq_conversation"),
    )

    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    sender_id: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    messages: Mapped[list["SocialMessage"]] = relationship(
        "SocialMessage", back_populates="conversation", order_by="SocialMessage.sent_at"
    )


class SocialMessage(UUIDPrimaryKey, Base):
    """A single message within a social DM conversation."""
    __tablename__ = "social_messages"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("social_conversations.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    conversation: Mapped["SocialConversation"] = relationship(
        "SocialConversation", back_populates="messages"
    )
