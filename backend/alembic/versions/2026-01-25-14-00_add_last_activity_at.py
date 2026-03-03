"""Add last_activity_at column to leads table

Revision ID: add_last_activity_at
Revises: fix_leads_updated_at
Create Date: 2026-01-25 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_last_activity_at'
down_revision: Union[str, Sequence[str], None] = 'fix_leads_updated_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add last_activity_at column to leads table."""
    op.add_column('leads',
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Remove last_activity_at column from leads table."""
    op.drop_column('leads', 'last_activity_at')
