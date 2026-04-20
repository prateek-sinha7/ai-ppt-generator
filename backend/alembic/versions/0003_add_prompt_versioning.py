"""Add prompt versioning to pipeline_executions

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add prompt versioning fields to pipeline_executions table"""
    
    # Add prompt_id field
    op.add_column(
        "pipeline_executions",
        sa.Column("prompt_id", sa.String(16), nullable=True),
    )
    
    # Add prompt_version field
    op.add_column(
        "pipeline_executions",
        sa.Column("prompt_version", sa.String(20), nullable=True),
    )
    
    # Add prompt_metadata JSONB field
    op.add_column(
        "pipeline_executions",
        sa.Column(
            "prompt_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    
    # Create index on prompt_id for faster lookups
    op.create_index(
        "ix_pipeline_executions_prompt_id",
        "pipeline_executions",
        ["prompt_id"],
    )


def downgrade() -> None:
    """Remove prompt versioning fields from pipeline_executions table"""
    
    # Drop index
    op.drop_index("ix_pipeline_executions_prompt_id", table_name="pipeline_executions")
    
    # Drop columns
    op.drop_column("pipeline_executions", "prompt_metadata")
    op.drop_column("pipeline_executions", "prompt_version")
    op.drop_column("pipeline_executions", "prompt_id")
