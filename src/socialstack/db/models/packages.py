from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from socialstack.db.base import Base, TimestampMixin, UUIDPrimaryKey


class ContentPackage(UUIDPrimaryKey, TimestampMixin, Base):
    """Service tier that defines how many posts per week and what types."""
    __tablename__ = "content_packages"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(50), default="monthly", nullable=False)
    posts_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    content_types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    items: Mapped[list["ContentPackageItem"]] = relationship(
        "ContentPackageItem", back_populates="package", lazy="selectin"
    )


class ContentPackageItem(UUIDPrimaryKey, Base):
    """One row per content type within a package."""
    __tablename__ = "content_package_items"

    package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("content_packages.id", ondelete="CASCADE"), nullable=False
    )
    content_types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    max_posts: Mapped[int] = mapped_column(Integer, nullable=False)
    period: Mapped[str] = mapped_column(String(20), default="week", nullable=False)

    package: Mapped["ContentPackage"] = relationship("ContentPackage", back_populates="items")
