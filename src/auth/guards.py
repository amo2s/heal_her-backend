import re
import hashlib
import httpx
import logging
import redis.asyncio as redis
from strawberry.permission import BasePermission
from strawberry.types import Info

# 1. Import your central settings
from core.config import settings

# [UPDATE]: Import the central Security Shield exceptions
from core.exceptions import (
    SecurityViolationError,
    AuthenticationError,
    ValidationError,
    InfrastructureError
)

# ---------------------------------------------------------
# PROFESSIONAL SECURITY LOGGING
# ---------------------------------------------------------
logger = logging.getLogger("HEAL_SECURITY_GUARD")
logger.setLevel(logging.WARNING)

# ---------------------------------------------------------
# VALKEY (REDIS) SETUP
# ---------------------------------------------------------
if not settings.REDIS_URL:
    raise ValueError("CRITICAL: REDIS_URL environment variable is missing in the vault!")

valkey_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# Expand this list as needed.
BURNER_DOMAINS = {
    "mailinator.com", "10minutemail.com", "tempmail.com", 
    "guerrillamail.com", "yopmail.com", "throwawaymail.com"
}


# =====================================================================
# 1. THE SIGNUP GUARD
# =====================================================================
class SignupFortressGuard(BasePermission):
    """
    Extremist Security Guard for the Signup Mutation.
    Executes multiple layers of defense before the resolver is ever touched.
    """
    message = "Access Denied." # Generic fallback message

    async def has_permission(self, source, info: Info, **kwargs) -> bool:
        request = info.context["request"]
        client_ip = request.client.host

        # [UPDATE]: Redis Fail-Safe added to ALL Valkey calls. 
        # If Redis blips, it logs an InfrastructureError internally but fails OPEN 
        # so legitimate users can still sign up, preventing a complete system outage.
        try:
            # --- LAYER 1: THE BLACKLIST CHECK ---
            is_blacklisted = await valkey_client.get(f"blacklist:{client_ip}")
            if is_blacklisted:
                # [UPDATE]: Replaced GraphQLError with SecurityViolationError.
                # Hacker sees: "Access denied. Invalid security context."
                # Terminal sees: "Blocked connection from Blacklisted IP: <IP>"
                raise SecurityViolationError(internal_message=f"Blocked connection from Blacklisted IP: {client_ip}")

            # --- LAYER 2: THE HANDSHAKE (FINGERPRINTING) ---
            handshake_secret = settings.FRONTEND_HANDSHAKE_SECRET
            client_handshake = request.headers.get("x-healher-handshake")
            
            if not handshake_secret or client_handshake != handshake_secret:
                raise SecurityViolationError(internal_message=f"Failed Handshake from IP: {client_ip}. Possible API bypass attempt.")

            # --- LAYER 3: VELOCITY SHIELD (RATE LIMITING) ---
            rate_key = f"rate_limit:signup:{client_ip}"
            attempts = await valkey_client.incr(rate_key)
            
            if attempts == 1:
                await valkey_client.expire(rate_key, 60)  # 60 seconds window
                
            if attempts > 5:
                if attempts > 20:
                    logger.error(f"SEVERE: IP {client_ip} exceeded absolute velocity limit. Blacklisting for 24h.")
                    await valkey_client.setex(f"blacklist:{client_ip}", 86400, "1")
                # [UPDATE]: Standardized rate limit message.
                raise SecurityViolationError(internal_message=f"Velocity limit exceeded for IP: {client_ip}")

        except redis.RedisError as e:
            # [UPDATE]: Trap Redis crashes. Don't crash the request.
            logger.error(f"[INFRASTRUCTURE SHIELD] Valkey connection failed during signup checks: {str(e)}")
            # We proceed with the request to fail-open, but we know the cache is down.

        # --- EXTRACT MUTATION KWARGS ---
        email = kwargs.get("email", "").lower().strip()
        password = kwargs.get("password", "")
        bot_trap = kwargs.get("bot_trap")

        # --- LAYER 4: THE HONEYPOT ---
        if bot_trap:
            try:
                await valkey_client.setex(f"blacklist:{client_ip}", 86400, "1")
            except redis.RedisError:
                pass # Fail silently if Redis is down
            # [UPDATE]: Generic public error, highly specific internal log.
            raise SecurityViolationError(internal_message=f"HONEYPOT TRIGGERED by IP: {client_ip}. Blacklisting for 24h.")

        # --- LAYER 5: BURNER EMAIL FILTER ---
        if email:
            domain = email.split("@")[-1]
            if domain in BURNER_DOMAINS:
                # [UPDATE]: Use ValidationError for bad inputs.
                raise ValidationError(
                    public_message="Real emails only, please. Disposable domains are blocked.",
                    internal_message=f"Burner email rejected: {email} from IP {client_ip}"
                )

        # --- LAYER 6: ENTROPY & PWNED PASSWORD CHECK ---
        if password:
            if len(password) < 8 or not re.search(r"[A-Z]", password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
                raise ValidationError(
                    public_message="Password must be 8+ chars, with an uppercase letter and a symbol.",
                    internal_message=f"Weak password attempt from {client_ip}"
                )
            
            sha1_pwd = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
            prefix, suffix = sha1_pwd[:5], sha1_pwd[5:]
            
            try:
                # [UPDATE]: Tightened timeout to 1.5s to prevent signup bottlenecks.
                async with httpx.AsyncClient(timeout=1.5) as client:
                    resp = await client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
                    if resp.status_code == 200:
                        if suffix in resp.text:
                            raise ValidationError(
                                public_message="This password has been exposed in a public data breach. Please choose a safer one.",
                                internal_message=f"Pwned password attempt blocked for IP {client_ip}"
                            )
            except httpx.RequestError as e:
                # [UPDATE]: Swallow the error into our Infrastructure logs and proceed so users aren't punished for an external API outage.
                logger.error(f"[INFRASTRUCTURE SHIELD] PwnedPasswords API timeout/error: {str(e)}. Bypassing check.")

        return True


# =====================================================================
# 2. THE LOGIN GUARD (THE DUAL-AXIS BEAR TRAP)
# =====================================================================
class LoginFortressGuard(BasePermission):
    """
    Extremist Security Guard for the Login Mutation.
    Implements the Dual-Axis Bear Trap to stop Brute Force and Credential Stuffing.
    """
    message = "Access Denied."

    async def has_permission(self, source, info, **kwargs) -> bool:
        request = info.context["request"]
        client_ip = request.client.host

        try:
            # --- LAYER 1: THE BLACKLIST CHECK ---
            is_blacklisted = await valkey_client.get(f"blacklist:{client_ip}")
            if is_blacklisted:
                raise SecurityViolationError(internal_message=f"Login attempt from blacklisted IP: {client_ip}")

            # --- LAYER 2: THE HANDSHAKE (FINGERPRINTING) ---
            handshake_secret = settings.FRONTEND_HANDSHAKE_SECRET
            client_handshake = request.headers.get("x-healher-handshake")
            
            if not handshake_secret or client_handshake != handshake_secret:
                raise SecurityViolationError(internal_message=f"Login Handshake failed for IP: {client_ip}")

            # --- EXTRACT KWARGS ---
            input_data = kwargs.get("input_data")
            if not input_data or not getattr(input_data, "email", None):
                raise ValidationError(public_message="Email is required.")

            email = input_data.email.lower().strip()

            # --- LAYER 3: THE IP-LEVEL TRAP (BRUTE FORCE CHECK) ---
            ip_fails = await valkey_client.get(f"login_fails_ip:{client_ip}")
            if ip_fails and int(ip_fails) >= 5:
                # [UPDATE]: Fixed the Identity Enumeration leak here.
                # Hacker sees: "Invalid credentials or session expired." (Same as a bad password)
                # Terminal sees: "IP Velocity Lockout triggered for <IP>"
                raise AuthenticationError(internal_message=f"IP Velocity Lockout triggered for {client_ip}")

            # --- LAYER 4: THE ACCOUNT-LEVEL TRAP (CREDENTIAL STUFFING CHECK) ---
            email_fails = await valkey_client.get(f"login_fails_email:{email}")
            if email_fails and int(email_fails) >= 5:
                # [UPDATE]: Fixed the Identity Enumeration leak here. 
                # We no longer tell the hacker the account is locked (which confirms the email exists).
                # We feed them the generic AuthenticationError bucket.
                raise AuthenticationError(internal_message=f"Account Lockout triggered for {email}")

        except redis.RedisError as e:
            # [UPDATE]: Prevent Redis downtime from locking out valid logins.
            logger.error(f"[INFRASTRUCTURE SHIELD] Valkey connection failed during login checks: {str(e)}")

        return True