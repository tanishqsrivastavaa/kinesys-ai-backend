"""Fix all lead column type mismatches between model and database

This migration comprehensively fixes all column type mismatches:
1. annual_revenue: NUMERIC -> VARCHAR(50)
2. employee_count: INTEGER -> VARCHAR(50)
3. interests: JSON -> JSONB with default []
4. custom_fields: JSON -> JSONB with default {}
5. lead_stage_history.changed_at: Add missing column
6. lead_stage_history.from_stage/to_stage: VARCHAR -> leadstage enum

Revision ID: fix_all_lead_column_types
Revises: add_lead_enum_types
Create Date: 2026-01-25 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'fix_all_lead_column_types'
down_revision: Union[str, Sequence[str], None] = 'add_lead_enum_types'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Fix all column type mismatches."""

    # ===========================================
    # FIX LEADS TABLE
    # ===========================================

    # 1. annual_revenue: NUMERIC(15,2) -> VARCHAR(50)
    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN annual_revenue TYPE VARCHAR(50)
        USING annual_revenue::VARCHAR(50);
    """)

    # 2. employee_count: INTEGER -> VARCHAR(50)
    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN employee_count TYPE VARCHAR(50)
        USING employee_count::VARCHAR(50);
    """)

    # 3. interests: JSON -> JSONB with default []
    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN interests TYPE JSONB USING interests::JSONB;
    """)
    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN interests SET DEFAULT '[]'::JSONB;
    """)
    op.execute("""
        UPDATE leads SET interests = '[]'::JSONB WHERE interests IS NULL;
    """)

    # 4. custom_fields: JSON -> JSONB with default {}
    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN custom_fields TYPE JSONB USING custom_fields::JSONB;
    """)
    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN custom_fields SET DEFAULT '{}'::JSONB;
    """)
    op.execute("""
        UPDATE leads SET custom_fields = '{}'::JSONB WHERE custom_fields IS NULL;
    """)

    # ===========================================
    # FIX LEAD_STAGE_HISTORY TABLE
    # ===========================================

    # 5. Add changed_at column if missing
    if not column_exists('lead_stage_history', 'changed_at'):
        op.add_column('lead_stage_history',
            sa.Column('changed_at', sa.DateTime(timezone=True),
                      server_default=sa.text('now()'), nullable=False)
        )

    # 6. Convert from_stage and to_stage to enum type
    op.execute("""
        ALTER TABLE lead_stage_history
        ALTER COLUMN from_stage TYPE leadstage USING from_stage::leadstage;
    """)
    op.execute("""
        ALTER TABLE lead_stage_history
        ALTER COLUMN to_stage TYPE leadstage USING to_stage::leadstage;
    """)


def downgrade() -> None:
    """Revert column type changes."""

    # Revert lead_stage_history changes
    op.execute("""
        ALTER TABLE lead_stage_history
        ALTER COLUMN from_stage TYPE VARCHAR(50);
    """)
    op.execute("""
        ALTER TABLE lead_stage_history
        ALTER COLUMN to_stage TYPE VARCHAR(50);
    """)
    op.drop_column('lead_stage_history', 'changed_at')

    # Revert leads changes
    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN custom_fields TYPE JSON USING custom_fields::JSON;
    """)
    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN custom_fields DROP DEFAULT;
    """)

    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN interests TYPE JSON USING interests::JSON;
    """)
    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN interests DROP DEFAULT;
    """)

    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN employee_count TYPE INTEGER USING employee_count::INTEGER;
    """)

    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN annual_revenue TYPE NUMERIC(15,2)
        USING annual_revenue::NUMERIC(15,2);
    """)
