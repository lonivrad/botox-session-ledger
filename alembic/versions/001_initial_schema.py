"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-15

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "practitioners",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "practitioner_id", sa.Integer(), sa.ForeignKey("practitioners.id"), nullable=True
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "vials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "practitioner_id", sa.Integer(), sa.ForeignKey("practitioners.id"), nullable=True
        ),
        sa.Column("product", sa.String(100), nullable=False, server_default="Botox"),
        sa.Column("lot_number", sa.String(100), nullable=True),
        sa.Column("units_total", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("units_remaining", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("diluent_ml", sa.Float(), nullable=False),
        sa.Column("concentration", sa.Float(), nullable=False),
        sa.Column("cost", sa.Float(), nullable=False, server_default="656.0"),
        sa.Column("expiry_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("unopened", "active", "depleted", "expired", name="vialstatus"),
            nullable=False,
            server_default="unopened",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column(
            "practitioner_id", sa.Integer(), sa.ForeignKey("practitioners.id"), nullable=True
        ),
        sa.Column("session_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pricing_mode", sa.String(50), nullable=False, server_default="standard"),
        sa.Column("client_charge", sa.Float(), nullable=True),
        sa.Column("custom_price_per_unit", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total_units", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_volume_ml", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_session_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("gross_margin", sa.Float(), nullable=True),
        sa.Column("gross_margin_percent", sa.Float(), nullable=True),
        sa.Column("recommended_charge", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "session_areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("area_name", sa.String(255), nullable=False),
        sa.Column("units", sa.Float(), nullable=False),
        sa.Column("volume_ml", sa.Float(), nullable=False),
        sa.Column("u100_markings", sa.Float(), nullable=False),
    )

    op.create_table(
        "vial_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vial_id", sa.Integer(), sa.ForeignKey("vials.id"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("units_allocated", sa.Float(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("vial_allocations")
    op.drop_table("session_areas")
    op.drop_table("sessions")
    op.drop_table("vials")
    op.drop_table("clients")
    op.drop_table("practitioners")
