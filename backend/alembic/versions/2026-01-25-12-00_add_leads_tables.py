"""Add leads, tags, and stage history tables

Revision ID: add_leads_tables
Revises: b598b7cf8942
Create Date: 2026-01-25 12:00:00.000000

"""
from typing import Sequence, Union
import sqlmodel
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'add_leads_tables'
down_revision: Union[str, Sequence[str], None] = 'b598b7cf8942'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: We use VARCHAR instead of native PostgreSQL enums for flexibility.
    # Python enums in the model provide validation; DB stores as strings.

    # Create tags table
    op.create_table('tags',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('color', sqlmodel.sql.sqltypes.AutoString(length=7), nullable=False, server_default='#3B82F6'),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'user_id', name='uq_tag_name_user')
    )
    op.create_index(op.f('ix_tags_id'), 'tags', ['id'], unique=False)
    op.create_index(op.f('ix_tags_user_id'), 'tags', ['user_id'], unique=False)
    op.create_index('ix_tags_user_name', 'tags', ['user_id', 'name'], unique=True)

    # Create leads table with correct types matching the model
    # Using VARCHAR for enum fields - Python enums validate, DB stores strings
    op.execute("""
        CREATE TABLE leads (
            id UUID PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE,
            deleted_at TIMESTAMP WITH TIME ZONE,
            is_active BOOLEAN NOT NULL DEFAULT true,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            email VARCHAR(255),
            phone VARCHAR(50),
            mobile_no VARCHAR(50),
            company VARCHAR(255),
            organization VARCHAR(255),
            website VARCHAR(500),
            job_title VARCHAR(100),
            industry VARCHAR(100),
            source VARCHAR(50) NOT NULL DEFAULT 'Other',
            stage VARCHAR(50) NOT NULL DEFAULT 'new',
            temperature VARCHAR(20) NOT NULL DEFAULT 'cold',
            lead_score INTEGER NOT NULL DEFAULT 0,
            annual_revenue VARCHAR(50),
            employee_count VARCHAR(50),
            territory VARCHAR(100),
            notes TEXT,
            last_activity_at TIMESTAMP WITH TIME ZONE,
            interests JSONB NOT NULL DEFAULT '[]'::JSONB,
            custom_fields JSONB NOT NULL DEFAULT '{}'::JSONB,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            assigned_to UUID REFERENCES users(id) ON DELETE SET NULL
        );
    """)
    op.create_index(op.f('ix_leads_id'), 'leads', ['id'], unique=False)
    op.create_index(op.f('ix_leads_user_id'), 'leads', ['user_id'], unique=False)
    op.create_index(op.f('ix_leads_assigned_to'), 'leads', ['assigned_to'], unique=False)
    op.create_index(op.f('ix_leads_stage'), 'leads', ['stage'], unique=False)
    op.create_index(op.f('ix_leads_email'), 'leads', ['email'], unique=False)
    op.create_index(op.f('ix_leads_company'), 'leads', ['company'], unique=False)
    op.create_index('ix_leads_user_stage', 'leads', ['user_id', 'stage'], unique=False)
    op.create_index('ix_leads_user_active', 'leads', ['user_id', 'is_active'], unique=False)

    # Create lead_tags junction table
    op.create_table('lead_tags',
        sa.Column('lead_id', sa.Uuid(), nullable=False),
        sa.Column('tag_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('lead_id', 'tag_id')
    )
    op.create_index('ix_lead_tags_lead_id', 'lead_tags', ['lead_id'], unique=False)
    op.create_index('ix_lead_tags_tag_id', 'lead_tags', ['tag_id'], unique=False)

    # Create lead_stage_history table with correct types
    # Using VARCHAR for stage fields - Python enums validate, DB stores strings
    op.execute("""
        CREATE TABLE lead_stage_history (
            id UUID PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE,
            lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
            from_stage VARCHAR(50),
            to_stage VARCHAR(50) NOT NULL,
            changed_by UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
            changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            notes TEXT
        );
    """)
    op.create_index(op.f('ix_lead_stage_history_id'), 'lead_stage_history', ['id'], unique=False)
    op.create_index(op.f('ix_lead_stage_history_lead_id'), 'lead_stage_history', ['lead_id'], unique=False)
    op.create_index('ix_lead_stage_history_changed_by', 'lead_stage_history', ['changed_by'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_lead_stage_history_lead_id'), table_name='lead_stage_history')
    op.drop_index(op.f('ix_lead_stage_history_id'), table_name='lead_stage_history')
    op.drop_table('lead_stage_history')

    op.drop_index('ix_lead_tags_tag_id', table_name='lead_tags')
    op.drop_index('ix_lead_tags_lead_id', table_name='lead_tags')
    op.drop_table('lead_tags')

    op.drop_index(op.f('ix_leads_company'), table_name='leads')
    op.drop_index(op.f('ix_leads_email'), table_name='leads')
    op.drop_index(op.f('ix_leads_stage'), table_name='leads')
    op.drop_index(op.f('ix_leads_assigned_to'), table_name='leads')
    op.drop_index(op.f('ix_leads_user_id'), table_name='leads')
    op.drop_index(op.f('ix_leads_id'), table_name='leads')
    op.drop_table('leads')

    op.drop_index(op.f('ix_tags_user_id'), table_name='tags')
    op.drop_index(op.f('ix_tags_id'), table_name='tags')
    op.drop_table('tags')
