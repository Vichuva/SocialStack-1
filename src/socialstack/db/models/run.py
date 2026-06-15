from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialstack.db.base import Base, TimestampMixin, UUIDPrimaryKey


class WorkflowRun(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "workflow_runs"

    workflow: Mapped[str] = mapped_column(String(100), nullable=False)
    business_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    trigger_kind: Mapped[str] = mapped_column(String(50), default="api", nullable=False)
    # trigger_kind: api | cron | manual
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    # status: queued | running | succeeded | failed
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
