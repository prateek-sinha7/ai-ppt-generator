"""Add design_spec column to presentations

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "presentations",
        sa.Column("design_spec", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("presentations", "design_spec")
