import hashlib
from typing import Any
from strawberry.permission import BasePermission
from strawberry.types import Info

from core.config import settings
from core.exceptions import AuthenticationError
# assuming your global async cache client is exported from core
from core.redis import valkey_client 

class PasswordResetGuard(BasePermission):
    """
    x50 Fortified Shield for OTP Recovery.
    Enforces Handshake, Dual-Axis Rate Limiting, and Brute-Force Lockouts.
    """
    
    # zero-information exception message
    message = "service unavailable or security protocol violation."

    async def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        request = info.context.get("request")
        if not request:
            raise AuthenticationError(internal_message="missing request context.")
        
        # 1. Hardware/Frontend Handshake Verification
        handshake = request.headers.get("x-healher-handshake")
        if not handshake or handshake != settings.FRONTEND_HANDSHAKE_SECRET:
            raise AuthenticationError(internal_message="unauthorized client handshake.")

        # 2. Immutable Device Fingerprinting
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for")
        ip_address = forwarded.split(",")[0].strip() if forwarded else client_ip
        user_agent = request.headers.get("user-agent", "unknown")
        
        fingerprint = hashlib.sha256(f"{ip_address}:{user_agent}".encode()).hexdigest()

        # Extract the target email securely from the GraphQL input arguments
        email = None
        if "input" in kwargs:
            email = getattr(kwargs["input"], "email", None)
        elif "email" in kwargs:
            email = kwargs["email"]

        # 3. Execution of the Valkey Matrix
        await self._enforce_ip_velocity(fingerprint)
        
        if email:
            # lowercased for strict caching consistency
            clean_email = email.lower().strip()
            await self._check_brute_force_lockout(clean_email)
            await self._enforce_email_velocity(clean_email)

        return True

    async def _enforce_ip_velocity(self, fingerprint: str) -> None:
        """
        Locks out an IP if they attempt more than 3 requests in 15 minutes (900s).
        """
        key = f"security:ratelimit:ip:{fingerprint}"
        count = await valkey_client.incr(key)
        if count == 1:
            await valkey_client.expire(key, 900)
        
        if count > 3:
            raise AuthenticationError(internal_message="ip velocity shield triggered.")

    async def _enforce_email_velocity(self, email: str) -> None:
        """
        Protects a specific user's inbox from being spammed by botnets.
        Max 3 OTP requests per 15 minutes.
        """
        key = f"security:ratelimit:email:{email}"
        count = await valkey_client.incr(key)
        if count == 1:
            await valkey_client.expire(key, 900)
            
        if count > 3:
            raise AuthenticationError(internal_message="email velocity shield triggered.")

    async def _check_brute_force_lockout(self, email: str) -> None:
        """
        The 3-Strike Rule constraint. If this key exists, the email is 
        currently banned from making OTP attempts due to previous failed guesses.
        """
        lock_key = f"security:lockout:email:{email}"
        is_locked = await valkey_client.get(lock_key)
        if is_locked:
            raise AuthenticationError(internal_message="brute-force lockout active.")