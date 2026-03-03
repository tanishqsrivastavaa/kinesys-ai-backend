"""Convert PostgreSQL native enums to VARCHAR for flexibility

Native PostgreSQL enums cause case-sensitivity issues with Python StrEnum.
Converting to VARCHAR allows Python-side validation while being flexible
in storage. The Python enum types still validate input in Pydantic schemas.

Revision ID: convert_enums_to_varchar
Revises: fix_all_lead_column_types
Create Date: 2026-01-25 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'convert_enums_to_varchar'
down_revision: Union[str, Sequence[str], None] = 'fix_all_lead_column_types'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert native PostgreSQL enums to VARCHAR."""

    # ==========================================
    # LEADS TABLE - Convert enum columns to VARCHAR
    # ==========================================

    # Drop defaults first
    op.execute("ALTER TABLE leads ALTER COLUMN source DROP DEFAULT;")
    op.execute("ALTER TABLE leads ALTER COLUMN stage DROP DEFAULT;")
    op.execute("ALTER TABLE leads ALTER COLUMN temperature DROP DEFAULT;")

    # Convert source: leadsource -> VARCHAR(50)
    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN source TYPE VARCHAR(50)
        USING source::TEXT;
    """)

    # Convert stage: leadstage -> VARCHAR(50)
    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN stage TYPE VARCHAR(50)
        USING stage::TEXT;
    """)

    # Convert temperature: leadtemperature -> VARCHAR(20)
    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN temperature TYPE VARCHAR(20)
        USING temperature::TEXT;
    """)

    # Set new defaults as strings
    op.execute("ALTER TABLE leads ALTER COLUMN source SET DEFAULT 'Other';")
    op.execute("ALTER TABLE leads ALTER COLUMN stage SET DEFAULT 'new';")
    op.execute("ALTER TABLE leads ALTER COLUMN temperature SET DEFAULT 'cold';")

    # ==========================================
    # LEAD_STAGE_HISTORY TABLE - Convert enum columns to VARCHAR
    # ==========================================

    # Convert from_stage: leadstage -> VARCHAR(50)
    op.execute("""
        ALTER TABLE lead_stage_history
        ALTER COLUMN from_stage TYPE VARCHAR(50)
        USING from_stage::TEXT;
    """)

    # Convert to_stage: leadstage -> VARCHAR(50)
    op.execute("""
        ALTER TABLE lead_stage_history
        ALTER COLUMN to_stage TYPE VARCHAR(50)
        USING to_stage::TEXT;
    """)

    # ==========================================
    # DROP UNUSED ENUM TYPES
    # ==========================================
    # We keep them for now in case of rollback, but they're no longer used
    # op.execute("DROP TYPE IF EXISTS leadsource;")
    # op.execute("DROP TYPE IF EXISTS leadstage;")
    # op.execute("DROP TYPE IF EXISTS leadtemperature;")


def downgrade() -> None:
    """Convert VARCHAR columns back to native PostgreSQL enums."""

    # Recreate enum types if they don't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE leadsource AS ENUM (
                'Website', 'LinkedIn', 'Referral', 'TradeShow',
                'ColdCall', 'Advertisement', 'Partner', 'Other'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE leadstage AS ENUM (
                'new', 'contacted', 'qualified', 'proposal',
                'negotiation', 'won', 'lost'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE leadtemperature AS ENUM ('hot', 'warm', 'cold');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # Convert back to enums
    op.execute("ALTER TABLE leads ALTER COLUMN source DROP DEFAULT;")
    op.execute("ALTER TABLE leads ALTER COLUMN stage DROP DEFAULT;")
    op.execute("ALTER TABLE leads ALTER COLUMN temperature DROP DEFAULT;")

    op.execute("ALTER TABLE leads ALTER COLUMN source TYPE leadsource USING source::leadsource;")
    op.execute("ALTER TABLE leads ALTER COLUMN stage TYPE leadstage USING stage::leadstage;")
    op.execute("ALTER TABLE leads ALTER COLUMN temperature TYPE leadtemperature USING temperature::leadtemperature;")

    op.execute("ALTER TABLE leads ALTER COLUMN source SET DEFAULT 'Other';")
    op.execute("ALTER TABLE leads ALTER COLUMN stage SET DEFAULT 'new';")
    op.execute("ALTER TABLE leads ALTER COLUMN temperature SET DEFAULT 'cold';")

    op.execute("ALTER TABLE lead_stage_history ALTER COLUMN from_stage TYPE leadstage USING from_stage::leadstage;")
    op.execute("ALTER TABLE lead_stage_history ALTER COLUMN to_stage TYPE leadstage USING to_stage::leadstage;")
