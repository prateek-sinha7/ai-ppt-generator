"""Increase topic column length from 500 to 5000

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "presentations",
        "topic",
        existing_type=sa.String(500),
        type_=sa.String(5000),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "presentations",
        "topic",
        existing_type=sa.String(5000),
        type_=sa.String(500),
        existing_nullable=False,
    )
