import logging
import redis.asyncio as redis
from core.config import settings
from core.exceptions import InfrastructureError

logger = logging.getLogger("HEAL_SECURITY")
logger.setLevel(logging.WARNING)

# ---------------------------------------------------------
# THE GLOBAL CACHE POOL (Singleton Instance)
# ---------------------------------------------------------
# decode_responses=True guarantees clean Python strings everywhere.
# the additional parameters ensure the connection pool heals itself if the network drops.
valkey_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    health_check_interval=30,
    socket_connect_timeout=5.0,
    retry_on_timeout=True,
    max_connections=100  # prevents choking the server under heavy load
)

async def verify_cache_connection() -> None:
    """
    Executes a rapid ping on FastAPI startup.
    If Valkey is down, it halts the boot sequence immediately.
    """
    try:
        await valkey_client.ping()
        logger.info("[INFRASTRUCTURE SHIELD] Valkey cache pool initialized securely.")
    except redis.RedisError as e:
        logger.critical(f"[FATAL NETWORK DROP] Cache engine unreachable: {str(e)}")
        raise InfrastructureError(
            internal_message="Central cache engine initialization failed."
        )