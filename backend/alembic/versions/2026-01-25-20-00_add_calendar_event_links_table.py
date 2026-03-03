"""Add calendar_event_links table

Revision ID: add_calendar_event_links
Revises: add_bookings_table
Create Date: 2026-01-25 20:00:00.000000

"""
from typing import Sequence, Union
import sqlmodel
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_calendar_event_links'
down_revision: Union[str, Sequence[str], None] = 'add_bookings_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create calendar_event_links table."""
    op.create_table('calendar_event_links',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('google_event_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('lead_id', sa.Uuid(), nullable=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('event_title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('event_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_calendar_event_links_id'), 'calendar_event_links', ['id'], unique=False)
    op.create_index(op.f('ix_calendar_event_links_google_event_id'), 'calendar_event_links', ['google_event_id'], unique=False)
    op.create_index(op.f('ix_calendar_event_links_lead_id'), 'calendar_event_links', ['lead_id'], unique=False)
    op.create_index(op.f('ix_calendar_event_links_user_id'), 'calendar_event_links', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop calendar_event_links table."""
    op.drop_index(op.f('ix_calendar_event_links_user_id'), table_name='calendar_event_links')
    op.drop_index(op.f('ix_calendar_event_links_lead_id'), table_name='calendar_event_links')
    op.drop_index(op.f('ix_calendar_event_links_google_event_id'), table_name='calendar_event_links')
    op.drop_index(op.f('ix_calendar_event_links_id'), table_name='calendar_event_links')
    op.drop_table('calendar_event_links')
