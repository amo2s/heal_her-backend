import re
import hashlib
import httpx
import logging
import redis.asyncio as redis
from strawberry.permission import BasePermission
from strawberry.types import Info
from graphql import GraphQLError

# 1. Import your central settings
from core.config import settings

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
    message = "Access Denied by Heal Her Security."

    async def has_permission(self, source, info: Info, **kwargs) -> bool:
        request = info.context["request"]
        client_ip = request.client.host

        # --- LAYER 1: THE BLACKLIST CHECK ---
        is_blacklisted = await valkey_client.get(f"blacklist:{client_ip}")
        if is_blacklisted:
            logger.warning(f"Blocked connection from Blacklisted IP: {client_ip}")
            raise GraphQLError("Access denied. IP is temporarily restricted.")

        # --- LAYER 2: THE HANDSHAKE (FINGERPRINTING) ---
        handshake_secret = settings.FRONTEND_HANDSHAKE_SECRET
        client_handshake = request.headers.get("x-healher-handshake")
        
        if not handshake_secret or client_handshake != handshake_secret:
            logger.warning(f"Failed Handshake from IP: {client_ip}. Possible API bypass attempt.")
            raise GraphQLError("Invalid client signature. Request rejected.")

        # --- LAYER 3: VELOCITY SHIELD (RATE LIMITING) ---
        rate_key = f"rate_limit:signup:{client_ip}"
        attempts = await valkey_client.incr(rate_key)
        
        if attempts == 1:
            await valkey_client.expire(rate_key, 60)  # 60 seconds window
            
        if attempts > 5:
            if attempts > 20:
                logger.error(f"SEVERE: IP {client_ip} exceeded absolute velocity limit. Blacklisting for 24h.")
                await valkey_client.setex(f"blacklist:{client_ip}", 86400, "1")
            raise GraphQLError("Too many signup attempts. Please wait a minute.")

        # --- EXTRACT MUTATION KWARGS ---
        email = kwargs.get("email", "").lower().strip()
        password = kwargs.get("password", "")
        bot_trap = kwargs.get("bot_trap")

        # --- LAYER 4: THE HONEYPOT ---
        if bot_trap:
            logger.error(f"HONEYPOT TRIGGERED by IP: {client_ip}. Blacklisting for 24h.")
            await valkey_client.setex(f"blacklist:{client_ip}", 86400, "1")
            raise GraphQLError("Security Honeypot triggered. IP Blacklisted.")

        # --- LAYER 5: BURNER EMAIL FILTER ---
        if email:
            domain = email.split("@")[-1]
            if domain in BURNER_DOMAINS:
                logger.info(f"Burner email rejected: {email} from IP {client_ip}")
                raise GraphQLError("Real emails only, please. Disposable domains are blocked.")

        # --- LAYER 6: ENTROPY & PWNED PASSWORD CHECK ---
        if password:
            if len(password) < 8 or not re.search(r"[A-Z]", password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
                raise GraphQLError("Password must be 8+ chars, with an uppercase letter and a symbol.")
            
            sha1_pwd = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
            prefix, suffix = sha1_pwd[:5], sha1_pwd[5:]
            
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
                    if resp.status_code == 200:
                        if suffix in resp.text:
                            logger.info(f"Pwned password attempt blocked for IP {client_ip}")
                            raise GraphQLError("This password has been exposed in a public data breach. Please choose a safer one.")
            except httpx.RequestError:
                # Fail open if the external API is down so legit users can still sign up
                logger.error("PwnedPasswords API timeout. Bypassing check.")
                pass

        return True


# =====================================================================
# 2. THE LOGIN GUARD (THE DUAL-AXIS BEAR TRAP)
# =====================================================================
class LoginFortressGuard(BasePermission):
    """
    Extremist Security Guard for the Login Mutation.
    Implements the Dual-Axis Bear Trap to stop Brute Force and Credential Stuffing.
    """
    message = "Access Denied by Heal Her Security."

    async def has_permission(self, source, info, **kwargs) -> bool:
        request = info.context["request"]
        client_ip = request.client.host

        # --- LAYER 1: THE BLACKLIST CHECK ---
        is_blacklisted = await valkey_client.get(f"blacklist:{client_ip}")
        if is_blacklisted:
            raise GraphQLError("Access denied. IP is temporarily restricted.")

        # --- LAYER 2: THE HANDSHAKE (FINGERPRINTING) ---
        handshake_secret = settings.FRONTEND_HANDSHAKE_SECRET
        client_handshake = request.headers.get("x-healher-handshake")
        
        if not handshake_secret or client_handshake != handshake_secret:
            raise GraphQLError("Invalid client signature. Request rejected.")

        # --- EXTRACT KWARGS ---
        input_data = kwargs.get("input_data")
        if not input_data or not getattr(input_data, "email", None):
            raise GraphQLError("Email is required.")

        email = input_data.email.lower().strip()

        # --- LAYER 3: THE IP-LEVEL TRAP (BRUTE FORCE CHECK) ---
        ip_fails = await valkey_client.get(f"login_fails_ip:{client_ip}")
        if ip_fails and int(ip_fails) >= 5:
            logger.warning(f"IP Velocity Lockout triggered for {client_ip}")
            raise GraphQLError("Too many failed attempts from this location. Locked for 15 minutes.")

        # --- LAYER 4: THE ACCOUNT-LEVEL TRAP (CREDENTIAL STUFFING CHECK) ---
        email_fails = await valkey_client.get(f"login_fails_email:{email}")
        if email_fails and int(email_fails) >= 5:
            logger.warning(f"Account Lockout triggered for {email}")
            raise GraphQLError("Account temporarily locked due to suspicious activity. Try again in 15 minutes.")

        return True