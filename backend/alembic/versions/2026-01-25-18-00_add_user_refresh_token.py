"""Add refresh token fields to users table

Adds refresh_token and refresh_token_expires columns for JWT refresh token
rotation mechanism. The refresh token is stored in the database to enable
rotation and revocation.

Revision ID: add_user_refresh_token
Revises: convert_enums_to_varchar
Create Date: 2026-01-25 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_user_refresh_token'
down_revision: Union[str, Sequence[str], None] = 'convert_enums_to_varchar'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add refresh token columns to users table."""
    # Add refresh_token column
    op.add_column(
        'users',
        sa.Column('refresh_token', sa.String(length=500), nullable=True)
    )

    # Add refresh_token_expires column
    op.add_column(
        'users',
        sa.Column('refresh_token_expires', sa.DateTime(timezone=True), nullable=True)
    )

    # Create index on refresh_token for fast token lookup
    op.create_index(
        'ix_users_refresh_token',
        'users',
        ['refresh_token'],
        unique=False
    )


def downgrade() -> None:
    """Remove refresh token columns from users table."""
    # Drop index first
    op.drop_index('ix_users_refresh_token', table_name='users')

    # Drop columns
    op.drop_column('users', 'refresh_token_expires')
    op.drop_column('users', 'refresh_token')
