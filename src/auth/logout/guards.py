import hashlib
import logging
from typing import Any, Dict
from fastapi import Request
import strawberry
from jose import jwt, JWTError

# central imports based on your heal her architecture
from core.config import settings
from core.exceptions import AuthenticationError
import redis.asyncio as redis

# initialize the valkey client (or import it from your db core if already centralized)
valkey_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

logger = logging.getLogger("HEAL_SECURITY")
logger.setLevel(logging.WARNING)

async def enforce_logout_guard(info: strawberry.Info, raw_token: str) -> Dict[str, Any]:
    """
    the x50 cryptographic bouncer.
    intercepts, dissects, and violently rejects tampered requests.
    """
    # 1. extract the raw fastapi request from strawberry's context
    try:
        request: Request = info.context["request"]
    except KeyError:
        logger.critical("[FIREWALL] graphql context missing raw fastapi request.")
        raise AuthenticationError(internal_message="Authentication failed.")

    # 2. device binding extraction
    forwarded_for = request.headers.get("x-forwarded-for")
    client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "unknown")

    try:
        # 3. the unverified domain peek (anti-spoofing shield)
        unverified_payload = jwt.get_unverified_claims(raw_token)
        security_domain = unverified_payload.get("role")
        
        if not security_domain:
            raise ValueError("missing security domain barrier.")

        # 4. strict cryptographic enforcement
        # we decode verifying the actual signature and expiration naturally
        payload = jwt.decode(
            raw_token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )

        if payload.get("role") != security_domain:
            raise ValueError("cross-domain spoofing detected.")

        jti = payload.get("jti")
        sub = payload.get("sub")
        exp = payload.get("exp")

        if not jti or not sub or not exp:
            raise ValueError("token missing critical tracking claims (jti/sub/exp).")

        # 5. premature blacklist evaluation (replay shield)
        # we hash the jti so raw token ids never touch the valkey cache directly
        jti_hash = hashlib.sha256(jti.encode()).hexdigest()
        blacklist_key = f"revoked_jti:{jti_hash}"

        is_blacklisted = await valkey_client.exists(blacklist_key)
        if is_blacklisted:
            raise ValueError("replay attack detected: token already blacklisted.")

        # pass the clean, verified payload and bindings to the service layer
        return {
            "jti_hash": jti_hash,
            "sub": sub,
            "exp": exp,
            "domain": security_domain,
            "client_ip": client_ip,
            "user_agent": user_agent
        }

    except (JWTError, ValueError, Exception) as e:
        # 6. the uniform blast shield
        # log the deep technical failure internally for the security team
        logger.error(
            f"[SHIELD BREACH] logout rejected for IP: {client_ip} | UA: {user_agent} | Reason: {str(e)}"
        )
        # raise a completely generic, deadpan error to the outside world
        # assuming AuthenticationError is set up to return a safe 400/401 to the client
        raise AuthenticationError(internal_message="Authentication failed.")