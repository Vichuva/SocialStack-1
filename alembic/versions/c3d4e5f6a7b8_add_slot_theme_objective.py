"""add theme objective package_item_id to content_slots

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("content_slots", sa.Column("theme", sa.String(500), nullable=True))
    op.add_column("content_slots", sa.Column("objective", sa.String(50), nullable=True))
    op.add_column("content_slots", sa.Column("package_item_id", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("content_slots", "package_item_id")
    op.drop_column("content_slots", "objective")
    op.drop_column("content_slots", "theme")
