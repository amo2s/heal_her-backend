import os
import sys
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# --- BULLETPROOF PATH FIX ---
# This points Alembic directly to the 'src' folder where your code lives
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC_DIR = os.path.join(BASE_DIR, 'src')

sys.path.insert(0, BASE_DIR)
sys.path.insert(0, SRC_DIR)

# Now these imports will work because 'src' is in the path
from core.config import settings
from db import Base # Ensure this is the unified Base you corrected

# --- IMPORT MODELS HERE ---
# Importing models registers them with Base.metadata for Autogenerate to work
from auth.models.signup import User 
from kids.ai_buddy.models import ChatSession, ChatMessage
from kids.videos.models import KidVideo, KidVideoProgress  # <--- REGISTERED FOR ISOLATION
# NEW: Registering the Management Fortress models
from management.auth.signup.models import Staff
# ---------------------------

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# THE DETECTOR: Enhanced to verify your isolated video tables and new staff tables
print(f"DEBUG: Tables detected by Alembic: {Base.metadata.tables.keys()}")

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection) -> None:
    """
    Synchronous helper required by Alembic to execute the actual migration context.
    """
    context.configure(
        connection=connection, 
        target_metadata=target_metadata
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """
    Creates an async engine and uses run_sync to tunnel Alembic's sync operations.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # THE BRUTAL FIX: Forces the parameter as a native integer, bypassing PgBouncer errors
        connect_args={"statement_cache_size": 0} 
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        
    await connectable.dispose()

def run_migrations_online() -> None:
    """
    Wraps the async execution in the standard asyncio event loop for Alembic.
    """
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()