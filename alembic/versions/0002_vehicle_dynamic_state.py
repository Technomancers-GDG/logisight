"""Add vehicle_dynamic_state table for static/dynamic schema separation.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-19 00:00:00.000000

This migration creates a dedicated table for the dynamic runtime properties
of vehicles (status, location, availability) that change during simulation
ticks.  The static vehicle configuration remains in the ``vehicles`` table
unchanged.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vehicle_dynamic_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'idle'")),
        sa.Column("current_facility_id", sa.Integer(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("available_at", sa.DateTime(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["vehicles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["current_facility_id"],
            ["facilities.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vehicle_id", name="uq_vehicle_dynamic_state_vehicle_id"),
    )
    op.create_index(
        "ix_vehicle_dynamic_state_vehicle_id",
        "vehicle_dynamic_state",
        ["vehicle_id"],
    )

    # Seed dynamic_state rows for existing vehicles (copy current values).
    op.execute(
        """
        INSERT INTO vehicle_dynamic_state
            (vehicle_id, status, current_facility_id, available_at, updated_at)
        SELECT
            id          AS vehicle_id,
            status,
            current_facility_id,
            available_at,
            updated_at
        FROM vehicles
        """
    )


def downgrade() -> None:
    op.drop_table("vehicle_dynamic_state")
