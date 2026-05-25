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
    [DEV MODE]: Rate limiting and lockouts temporarily disabled so u can test freely!
    """
    
    # zero-information exception message
    message = "service unavailable or security protocol violation."

    async def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        request = info.context.get("request")
        if not request:
            raise AuthenticationError(internal_message="missing request context.")
        
        # 1. Hardware/Frontend Handshake Verification (We keep this since frontend is sending it properly now!)
        handshake = request.headers.get("x-healher-handshake")
        if not handshake or handshake != settings.FRONTEND_HANDSHAKE_SECRET:
            raise AuthenticationError(internal_message="unauthorized client handshake.")

        # [TEMP DEV BYPASS]: We are skipping the IP fingerprinting and Valkey Matrix checks 
        # entirely right here. It will just instantly return True and let u through every time!
        
        return True

    # keeping the functions down here intact so we can easily wire them back up for production later!
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