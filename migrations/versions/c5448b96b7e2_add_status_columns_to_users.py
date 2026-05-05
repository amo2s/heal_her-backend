"""add status columns to users

Revision ID: c5448b96b7e2
Revises: bd9470d6ff33
Create Date: 2026-05-01 20:42:41.434381

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# --- ALEMBIC METADATA (DO NOT REMOVE) ---
revision: str = 'c5448b96b7e2'
down_revision: Union[str, None] = 'bd9470d6ff33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
# ----------------------------------------

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Get current columns to avoid "DuplicateColumn" errors
    columns = [c['name'] for c in inspector.get_columns('users')]

    # 1. Only add 'is_active' if it doesn't exist
    if 'is_active' not in columns:
        op.add_column(
            'users', 
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true')
        )
        op.alter_column('users', 'is_active', server_default=None)
    
    # 2. Only add 'is_verified' if it doesn't exist
    if 'is_verified' not in columns:
        op.add_column(
            'users', 
            sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false')
        )
        op.alter_column('users', 'is_verified', server_default=None)

def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = [c['name'] for c in inspector.get_columns('users')]

    if 'is_verified' in columns:
        op.drop_column('users', 'is_verified')
    if 'is_active' in columns:
        op.drop_column('users', 'is_active')