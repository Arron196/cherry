"""add co2_ppm, vibration_g, supply_chain_stage to events

Revision ID: 20260214_0100
Revises: 20260210_0400
Create Date: 2026-02-14 01:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260214_0100"
down_revision: Union[str, None] = "20260210_0400"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("co2_ppm", sa.Float(), nullable=True))
    op.add_column("events", sa.Column("vibration_g", sa.Float(), nullable=True))
    op.add_column("events", sa.Column("supply_chain_stage", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "supply_chain_stage")
    op.drop_column("events", "vibration_g")
    op.drop_column("events", "co2_ppm")
