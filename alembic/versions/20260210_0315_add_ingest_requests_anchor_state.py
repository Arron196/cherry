"""add ingest request state tracking

Revision ID: 20260210_0315
Revises: 20260210_0201
Create Date: 2026-02-10 03:15:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260210_0315"
down_revision: Union[str, None] = "20260210_0201"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingest_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("ingest_status", sa.String(length=32), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        op.f("ix_ingest_requests_idempotency_key"),
        "ingest_requests",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(op.f("ix_ingest_requests_event_id"), "ingest_requests", ["event_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ingest_requests_event_id"), table_name="ingest_requests")
    op.drop_index(op.f("ix_ingest_requests_idempotency_key"), table_name="ingest_requests")
    op.drop_table("ingest_requests")
