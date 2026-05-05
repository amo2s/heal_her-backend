"""add age to users table

Revision ID: bd9470d6ff33
Revises: e98b19697abb
Create Date: 2026-05-01 20:34:48.783448

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd9470d6ff33'
down_revision: Union[str, Sequence[str], None] = 'e98b19697abb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Adds the 'age' column to the 'users' table.
    We use a server_default of '18' to ensure existing rows 
    do not violate the NOT NULL constraint.
    """
    # 1. Add the column with a temporary server default
    op.add_column(
        'users', 
        sa.Column('age', sa.Integer(), nullable=False, server_default='18')
    )
    
    # 2. Remove the server default so future inserts 
    # must explicitly provide an age via the application.
    op.alter_column('users', 'age', server_default=None)


def downgrade() -> None:
    """Removes the 'age' column from the 'users' table."""
    op.drop_column('users', 'age')