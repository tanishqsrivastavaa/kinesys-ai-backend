"""Add PostgreSQL enum types for leads

Revision ID: add_lead_enum_types
Revises: add_last_activity_at
Create Date: 2026-01-25 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'add_lead_enum_types'
down_revision: Union[str, Sequence[str], None] = 'add_last_activity_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create PostgreSQL enum types for lead fields."""
    # Create leadsource enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE leadsource AS ENUM (
                'Website', 'LinkedIn', 'Referral', 'TradeShow',
                'ColdCall', 'Advertisement', 'Partner', 'Other'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create leadstage enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE leadstage AS ENUM (
                'new', 'contacted', 'qualified', 'proposal',
                'negotiation', 'won', 'lost'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create leadtemperature enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE leadtemperature AS ENUM ('hot', 'warm', 'cold');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Drop defaults, alter column types, then set new defaults
    op.execute("ALTER TABLE leads ALTER COLUMN source DROP DEFAULT;")
    op.execute("ALTER TABLE leads ALTER COLUMN stage DROP DEFAULT;")
    op.execute("ALTER TABLE leads ALTER COLUMN temperature DROP DEFAULT;")

    op.execute("ALTER TABLE leads ALTER COLUMN source TYPE leadsource USING source::leadsource;")
    op.execute("ALTER TABLE leads ALTER COLUMN stage TYPE leadstage USING stage::leadstage;")
    op.execute("ALTER TABLE leads ALTER COLUMN temperature TYPE leadtemperature USING temperature::leadtemperature;")

    op.execute("ALTER TABLE leads ALTER COLUMN source SET DEFAULT 'Other';")
    op.execute("ALTER TABLE leads ALTER COLUMN stage SET DEFAULT 'new';")
    op.execute("ALTER TABLE leads ALTER COLUMN temperature SET DEFAULT 'cold';")


def downgrade() -> None:
    """Revert enum types to VARCHAR."""
    op.execute("""
        ALTER TABLE leads
        ALTER COLUMN source TYPE VARCHAR(50),
        ALTER COLUMN stage TYPE VARCHAR(50),
        ALTER COLUMN temperature TYPE VARCHAR(20);
    """)

    op.execute("DROP TYPE IF EXISTS leadsource;")
    op.execute("DROP TYPE IF EXISTS leadstage;")
    op.execute("DROP TYPE IF EXISTS leadtemperature;")
