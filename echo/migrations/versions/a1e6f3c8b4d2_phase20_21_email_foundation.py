"""phase20-21 email foundation

Revision ID: a1e6f3c8b4d2
Revises: 5d13b69d13f9
Create Date: 2026-07-22 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1e6f3c8b4d2"
down_revision: str | None = "5d13b69d13f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_credentials",
        sa.Column("credential_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("encrypted_access_token", sa.String(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.String(), nullable=False),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("credential_id"),
    )
    op.create_index(
        op.f("ix_email_credentials_user_id"), "email_credentials", ["user_id"], unique=True
    )
    op.create_table(
        "email_messages",
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider_message_id", sa.String(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("snippet", sa.String(), nullable=False),
        sa.Column("from_address", sa.String(), nullable=False),
        sa.Column("to_addresses", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("label_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_unread", sa.Boolean(), nullable=False),
        sa.Column("attachments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rfc_message_id", sa.String(), nullable=True),
        sa.Column("classification_category", sa.String(), nullable=True),
        sa.Column("classification_needs_response", sa.Boolean(), nullable=True),
        sa.Column(
            "classification_action_items", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("classification_classified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index(op.f("ix_email_messages_date"), "email_messages", ["date"], unique=False)
    op.create_index(
        op.f("ix_email_messages_provider_message_id"),
        "email_messages",
        ["provider_message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_messages_thread_id"), "email_messages", ["thread_id"], unique=False
    )
    op.create_index(op.f("ix_email_messages_user_id"), "email_messages", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_messages_user_id"), table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_thread_id"), table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_provider_message_id"), table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_date"), table_name="email_messages")
    op.drop_table("email_messages")
    op.drop_index(op.f("ix_email_credentials_user_id"), table_name="email_credentials")
    op.drop_table("email_credentials")
