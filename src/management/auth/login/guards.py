import asyncio
import logging
import typing
import strawberry
from strawberry.permission import BasePermission
from strawberry.types import Info
from fastapi import Request
from redis.asyncio import Redis, from_url

from core.config import settings

logger = logging.getLogger(__name__)

# =====================================================================
# THE VALKEY CACHE ENGINE (Extremist Connection Pool)
# =====================================================================
# We initialize this globally so the connection pool is reused
# across all login attempts, preventing socket exhaustion under heavy load.
valkey_client: Redis = from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_timeout=5.0,
    socket_connect_timeout=5.0,
    retry_on_timeout=True
)

class LoginBouncerGuard(BasePermission):
    """
    The Extremist Perimeter Bouncer for Management Authentication.
    Now Domain-Aware: Dynamically adapts defenses based on the specific door (Login vs Refresh).
    """
    message = "Security Violation: Access Denied."

    async def has_permission(self, source: typing.Any, info: Info, **kwargs) -> bool:
        # Strawberry typically passes request via context dict
        request: Request = info.context.get("request")
        if not request:
            self.message = "System Failure: Execution context breached."
            return False

        # Determine which door is being accessed (e.g., 'adminLogin' vs 'adminRefreshToken')
        target_mutation = info.field_name or "unknown"

        # =====================================================================
        # 1. THE PROXY PIN & IP EXTRACTION
        # =====================================================================
        # Prioritize the Proxy's forwarded IP. If bypassed, fall back to socket IP.
        forwarded_for = request.headers.get("x-forwarded-for")
        true_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host

        # =====================================================================
        # 2. THE GLOBAL KILL-SWITCH (Instant Lockdown Check)
        # =====================================================================
        try:
            # Check Valkey for a manual lockdown override flag
            is_lockdown = await valkey_client.get("SYSTEM_LOCKDOWN:MANAGEMENT")
            if is_lockdown == "1":
                # Hard Fail: Do not ghost. Sever the connection entirely.
                self.message = "Management Portal is currently under high-security lockdown."
                return False
        except Exception as e:
            logger.error(f"[VALKEY FATAL] Security Infrastructure Failure: {e}")
            # FAIL-CLOSED: If the security cache dies, assume compromise and drop traffic.
            self.message = "Security Infrastructure Unavailable."
            return False

        # =====================================================================
        # 3. BEHAVIORAL ANALYSIS & THE "SILENT DEATH" FLAG
        # =====================================================================
        is_ghost = False
        client_handshake = request.headers.get("x-healher-handshake")
        
        # If the cryptographic handshake from your Next.js proxy is missing or invalid:
        if not client_handshake or client_handshake != settings.FRONTEND_HANDSHAKE_SECRET:
            is_ghost = True

        # Fingerprint extraction: Automated scripts often omit standard headers.
        user_agent = request.headers.get("user-agent")
        if not user_agent or len(user_agent) < 10:
            is_ghost = True

        # =====================================================================
        # 4. CONTEXT-AWARE TRAFFIC CONTROL (The Logical Fork)
        # =====================================================================
        try:
            if "login" in target_mutation.lower():
                # --- THE HEAVY TARPIT (For Brute-Force Password Protection) ---
                tarpit_key = f"TARPIT:LOGIN_IP:{true_ip}"
                attempts = await valkey_client.incr(tarpit_key)
                if attempts == 1:
                    await valkey_client.expire(tarpit_key, 3600) # Track for 1 hour
                
                if attempts > 3:
                    # Geometric delay: 2^(attempts - 3). 
                    delay = min(2 ** (attempts - 3), 60)
                    await asyncio.sleep(delay)
                    
                    if attempts > 10:
                        is_ghost = True

            elif "refresh" in target_mutation.lower():
                # --- THE LIGHT SHIELD (For Token Rotation) ---
                # We do NOT sleep here. React StrictMode or spotty internet can cause 
                # legitimate double-refreshes. Sleeping would break the UI.
                # Instead, we just cap the absolute maximum to prevent server DoS.
                tarpit_key = f"TARPIT:REFRESH_IP:{true_ip}"
                attempts = await valkey_client.incr(tarpit_key)
                if attempts == 1:
                    await valkey_client.expire(tarpit_key, 60) # Only track for 1 minute
                
                if attempts > 20: 
                    # Over 20 refreshes in 1 minute from the same IP is an active attack.
                    logger.warning(f"[REFRESH FLOOD DETECTED] IP: {true_ip}")
                    is_ghost = True

        except Exception as e:
            logger.error(f"[VALKEY ERROR] Traffic Control Engine Failed: {e}")
            self.message = "Security Verification Failed."
            return False

        # =====================================================================
        # 5. ZERO-TRUST CONTEXT INJECTION
        # =====================================================================
        # We physically inject the gathered intelligence into the GraphQL context.
        info.context["security_intel"] = {
            "true_ip": true_ip,
            "user_agent": user_agent or "unknown",
            "is_ghost": is_ghost
        }

        # We MUST return True here to pass the Guard, so the resolver can execute Ghost/Error logic.
        return True