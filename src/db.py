from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from core.config import settings

# ---------------------------------------------------------
# 1. THE IMPENETRABLE ASYNC ENGINE (PgBouncer Shield)
# ---------------------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,
    
    # FIX: Disable caching strictly at the asyncpg driver level.
    # These specific keys tell the driver: "Don't use pre-prepared statements."
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
    
    # ADVANCED: Defensive Pooling
    pool_size=10,           # Keep 10 connections warm
    max_overflow=20,        # Allow burst traffic
    pool_timeout=30,        # Fail gracefully if DB is stuck
    pool_recycle=1800,      # Kill old connections every 30 mins
    pool_pre_ping=True,     # Always check if the connection is alive
    echo=False,             # Keep terminal logs clean
)

# ---------------------------------------------------------
# 2. ASYNC SESSION FACTORY
# ---------------------------------------------------------
# expire_on_commit=False prevents "Missing Object" errors after saves.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# ALIASES: Ensures all services and background workers find the factory
SessionLocal = AsyncSessionLocal
async_session_maker = AsyncSessionLocal

# ---------------------------------------------------------
# 3. BASE CLASS
# ---------------------------------------------------------
Base = declarative_base()

# ---------------------------------------------------------
# 4. ASYNC DEPENDENCY
# ---------------------------------------------------------
async def get_db():
    """
    Standard database dependency for FastAPI.
    Ensures that every request gets its own clean connection.
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except Exception:
            # If any part of the request fails, we undo everything 
            # to keep the database clean.
            await db.rollback()
            raise
        finally:
            # The context manager 'async with' handles this, 
            # but we call it explicitly for absolute safety.
            await db.close()