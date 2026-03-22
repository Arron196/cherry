"""add device and key management tables

Revision ID: 20260210_0400
Revises: 20260210_0315
Create Date: 2026-02-10 04:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260210_0400"
down_revision: Union[str, None] = "20260210_0315"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "managed_devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("disabled_reason", sa.Text(), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
    )
    op.create_index(op.f("ix_managed_devices_device_id"), "managed_devices", ["device_id"], unique=True)

    op.create_table(
        "managed_device_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("key_id", sa.String(length=128), nullable=False),
        sa.Column("algorithm", sa.String(length=64), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["managed_devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_id"),
    )
    op.create_index(op.f("ix_managed_device_keys_device_id"), "managed_device_keys", ["device_id"], unique=False)
    op.create_index(op.f("ix_managed_device_keys_key_id"), "managed_device_keys", ["key_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_managed_device_keys_key_id"), table_name="managed_device_keys")
    op.drop_index(op.f("ix_managed_device_keys_device_id"), table_name="managed_device_keys")
    op.drop_table("managed_device_keys")
    op.drop_index(op.f("ix_managed_devices_device_id"), table_name="managed_devices")
    op.drop_table("managed_devices")
