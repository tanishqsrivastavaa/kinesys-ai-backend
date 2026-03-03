"""Add bookings table

Revision ID: add_bookings_table
Revises: 331df797ed0a
Create Date: 2026-01-25 19:00:00.000000

"""
from typing import Sequence, Union
import sqlmodel
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_bookings_table'
down_revision: Union[str, Sequence[str], None] = '331df797ed0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create bookings table."""
    op.create_table('bookings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('appointment_datetime', sa.DateTime(timezone=True), nullable=False),
        sa.Column('timezone', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('first_name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('last_name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('phone', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('contact_id', sa.Uuid(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False, server_default='confirmed'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('appointment_datetime', 'is_active', name='uq_booking_slot_active')
    )
    op.create_index(op.f('ix_bookings_id'), 'bookings', ['id'], unique=False)
    op.create_index(op.f('ix_bookings_appointment_datetime'), 'bookings', ['appointment_datetime'], unique=False)
    op.create_index(op.f('ix_bookings_email'), 'bookings', ['email'], unique=False)
    op.create_index(op.f('ix_bookings_contact_id'), 'bookings', ['contact_id'], unique=False)


def downgrade() -> None:
    """Drop bookings table."""
    op.drop_index(op.f('ix_bookings_contact_id'), table_name='bookings')
    op.drop_index(op.f('ix_bookings_email'), table_name='bookings')
    op.drop_index(op.f('ix_bookings_appointment_datetime'), table_name='bookings')
    op.drop_index(op.f('ix_bookings_id'), table_name='bookings')
    op.drop_table('bookings')
