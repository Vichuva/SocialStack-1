"""PRD schema alignment — add variant review, packages, DM inbox, slot fields

Revision ID: a1b2c3d4e5f6
Revises: fd1478f5b0f4
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "fd1478f5b0f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── content_slots ────────────────────────────────────────────────────────
    op.add_column("content_slots", sa.Column("problem", sa.Text(), nullable=True))
    op.add_column("content_slots", sa.Column("solution", sa.Text(), nullable=True))
    op.add_column("content_slots", sa.Column("impact", sa.Text(), nullable=True))
    op.add_column(
        "content_slots",
        sa.Column("generation_attempt", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "content_slots",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── content_variants ─────────────────────────────────────────────────────
    op.add_column("content_variants", sa.Column("content", sa.Text(), nullable=True))
    op.add_column(
        "content_variants",
        sa.Column("review_status", sa.String(50), nullable=False, server_default="pending"),
    )
    op.add_column(
        "content_variants",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "content_variants",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column("content_variants", sa.Column("feedback_text", sa.Text(), nullable=True))
    op.add_column(
        "content_variants",
        sa.Column("regeneration_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "content_variants", sa.Column("platform_post_id", sa.String(255), nullable=True)
    )
    op.add_column(
        "content_variants",
        sa.Column("generation_metadata", postgresql.JSONB(), nullable=True),
    )
    # Backfill content from caption for existing rows
    op.execute("UPDATE content_variants SET content = caption WHERE content IS NULL")

    # ── social_platform_connections ──────────────────────────────────────────
    op.add_column(
        "social_platform_connections",
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "social_platform_connections",
        sa.Column("connection_config_enc", sa.String(2048), nullable=True),
    )
    # Backfill connection_config_enc from access_token_enc
    op.execute(
        "UPDATE social_platform_connections SET connection_config_enc = access_token_enc "
        "WHERE connection_config_enc IS NULL"
    )

    # ── business_preferences ─────────────────────────────────────────────────
    op.add_column("business_preferences", sa.Column("package_id", sa.String(36), nullable=True))
    op.add_column(
        "business_preferences",
        sa.Column("posting_schedule", postgresql.JSONB(), nullable=True),
    )

    # ── content_packages ─────────────────────────────────────────────────────
    op.create_table(
        "content_packages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("billing_cycle", sa.String(50), nullable=False, server_default="monthly"),
        sa.Column("posts_per_week", sa.Integer(), nullable=False),
        sa.Column("content_types", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── content_package_items ─────────────────────────────────────────────────
    op.create_table(
        "content_package_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("package_id", sa.String(36), nullable=False),
        sa.Column("content_types", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("max_posts", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(20), nullable=False, server_default="week"),
    )

    # ── Seed content packages ─────────────────────────────────────────────────
    import uuid

    starter_id = str(uuid.uuid4())
    standard_id = str(uuid.uuid4())
    premium_id = str(uuid.uuid4())

    op.execute(f"""
        INSERT INTO content_packages (id, name, billing_cycle, posts_per_week, content_types, is_active)
        VALUES
          ('{starter_id}',  'Starter',  'monthly', 5,  ARRAY['Text + Image'],   true),
          ('{standard_id}', 'Standard', 'monthly', 4,  ARRAY['Text + Image', 'Text + Video'], true),
          ('{premium_id}',  'Premium',  'monthly', 10, ARRAY['Text only'],       true)
    """)

    starter_item_id = str(uuid.uuid4())
    standard_item1_id = str(uuid.uuid4())
    standard_item2_id = str(uuid.uuid4())
    premium_item_id = str(uuid.uuid4())

    op.execute(f"""
        INSERT INTO content_package_items (id, package_id, content_types, max_posts, period)
        VALUES
          ('{starter_item_id}',   '{starter_id}',  ARRAY['Text + Image'],  5, 'week'),
          ('{standard_item1_id}', '{standard_id}', ARRAY['Text + Image'],  3, 'week'),
          ('{standard_item2_id}', '{standard_id}', ARRAY['Text + Video'],  1, 'week'),
          ('{premium_item_id}',   '{premium_id}',  ARRAY['Text only'],    10, 'week')
    """)

    # ── social_conversations ──────────────────────────────────────────────────
    op.create_table(
        "social_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "business_id",
            sa.String(36),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("sender_id", sa.String(255), nullable=False),
        sa.Column("sender_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("business_id", "platform", "sender_id", name="uq_conversation"),
    )

    # ── social_messages ───────────────────────────────────────────────────────
    op.create_table(
        "social_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("social_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "business_id",
            sa.String(36),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("social_messages")
    op.drop_table("social_conversations")
    op.drop_table("content_package_items")
    op.drop_table("content_packages")
    op.drop_column("business_preferences", "posting_schedule")
    op.drop_column("business_preferences", "package_id")
    op.drop_column("social_platform_connections", "connection_config_enc")
    op.drop_column("social_platform_connections", "last_verified_at")
    op.drop_column("content_variants", "generation_metadata")
    op.drop_column("content_variants", "platform_post_id")
    op.drop_column("content_variants", "regeneration_count")
    op.drop_column("content_variants", "feedback_text")
    op.drop_column("content_variants", "is_active")
    op.drop_column("content_variants", "is_current")
    op.drop_column("content_variants", "review_status")
    op.drop_column("content_variants", "content")
    op.drop_column("content_slots", "approved_at")
    op.drop_column("content_slots", "generation_attempt")
    op.drop_column("content_slots", "impact")
    op.drop_column("content_slots", "solution")
    op.drop_column("content_slots", "problem")
