import logging
from datetime import datetime, timezone
from fastapi import BackgroundTasks
import redis.asyncio as redis
from redis.exceptions import RedisError

# central imports based on your heal her architecture
from core.config import settings
from core.exceptions import InfrastructureError

logger = logging.getLogger("HEAL_SECURITY")
logger.setLevel(logging.WARNING)

valkey_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def _audit_logout_event(sub: str, domain: str, ip: str, user_agent: str):
    """
    non-blocking background worker to stream security events.
    """
    # in reality, this ships to your SIEM, datadog, or central db
    logger.info(
        f"[SECURITY AUDIT] user {sub} ({domain}) logged out securely. IP: {ip} | UA: {user_agent}"
    )

async def execute_logout_service(
    clean_payload: dict,
    background_tasks: BackgroundTasks
) -> bool:
    """
    the atomic vault.
    commits the hashed jti to valkey, calculates strict ttl, and fires async audits.
    """
    jti_hash = clean_payload["jti_hash"]
    exp_timestamp = clean_payload["exp"]
    
    # 1. dynamic ttl calculation with a 60-second clock-skew buffer
    current_time = int(datetime.now(timezone.utc).timestamp())
    
    # if token is somehow already naturally dead but passed the guard, give it a baseline 60s
    ttl = max(60, exp_timestamp - current_time + 60)
    
    blacklist_key = f"revoked_jti:{jti_hash}"

    try:
        # 2. memory optimized O(1) storage using a static flag "1"
        await valkey_client.set(blacklist_key, "1", ex=ttl)
        
        # 3. fire the non-blocking security audit pipeline
        background_tasks.add_task(
            _audit_logout_event,
            sub=clean_payload["sub"],
            domain=clean_payload["domain"],
            ip=clean_payload["client_ip"],
            user_agent=clean_payload["user_agent"]
        )
        
        return True

    except RedisError as e:
        # 4. the infrastructure circuit breaker
        logger.critical(f"[INFRASTRUCTURE DOWN] valkey failed during logout revocation: {str(e)}")
        raise InfrastructureError(
            internal_message="Valkey cache unavailable during session revocation."
        )