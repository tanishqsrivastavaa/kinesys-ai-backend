"""Add updated_at column to leads tables if missing

Revision ID: fix_leads_updated_at
Revises: add_leads_tables
Create Date: 2026-01-25 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'fix_leads_updated_at'
down_revision: Union[str, Sequence[str], None] = 'add_leads_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Add missing columns to tables."""
    # Add updated_at to leads if missing
    if not column_exists('leads', 'updated_at'):
        op.add_column('leads',
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
        )

    # Add last_activity_at to leads if missing
    if not column_exists('leads', 'last_activity_at'):
        op.add_column('leads',
            sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True)
        )

    # Add updated_at to tags if missing
    if not column_exists('tags', 'updated_at'):
        op.add_column('tags',
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
        )

    # Add updated_at to lead_stage_history if missing
    if not column_exists('lead_stage_history', 'updated_at'):
        op.add_column('lead_stage_history',
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    """Remove updated_at columns (only if this migration added them)."""
    # We don't remove the columns on downgrade since they might have been
    # created by the original migration
    pass
