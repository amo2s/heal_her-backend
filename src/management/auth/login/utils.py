import uuid
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from redis.asyncio import Redis, from_url

from core.config import settings

logger = logging.getLogger(__name__)

# =====================================================================
# LAYER 1: SECRET ISOLATION & ENTROPY CHECK
# =====================================================================
# We isolate the management keys from the main application.
# If the key is weak or missing, the Forge physically refuses to compile.
MANAGEMENT_SECRET = getattr(settings, "MANAGEMENT_JWT_SECRET_KEY", None)
if not MANAGEMENT_SECRET or len(MANAGEMENT_SECRET) < 64:
    raise RuntimeError("CRITICAL: MANAGEMENT_JWT_SECRET_KEY is missing or lacks minimum 64-character entropy.")

ALGORITHM = "HS256"

# Shared Valkey connection pool for high-speed I/O
valkey_client: Redis = from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_timeout=5.0
)

class TokenForge:
    """
    The Cryptographic Engine for the Management Domain.
    Issues Blood-Bound, Tracked, and Obfuscated JWTs.
    """

    @staticmethod
    def _generate_env_fingerprint(ip: str, user_agent: str) -> str:
        """
        LAYER 3: ENVIRONMENTAL PINNING
        Creates a one-way hash of the user's physical digital footprint.
        """
        raw_fingerprint = f"{ip}|{user_agent}|{MANAGEMENT_SECRET[-10:]}"
        return hashlib.sha256(raw_fingerprint.encode()).hexdigest()

    @classmethod
    async def issue_token_pair(cls, staff_id: str, ip: str, user_agent: str) -> tuple[str, str]:
        """
        Generates the Access and Refresh tokens, binding them to the environment
        and registering their JTIs in the Valkey cache.
        """
        env_hash = cls._generate_env_fingerprint(ip, user_agent)
        
        access_jti = str(uuid.uuid4())
        refresh_jti = str(uuid.uuid4())
        
        now = datetime.now(timezone.utc)
        
        # Access Token: 15 Minutes
        access_exp = now + timedelta(minutes=15)
        # Refresh Token: 7 Days
        refresh_exp = now + timedelta(days=7)

        # LAYER 5: OBFUSCATED CLAIMS
        # sid = Staff ID | env = Fingerprint | typ = Token Type | jti = Unique ID
        access_payload = {
            "sid": staff_id,
            "env": env_hash,
            "typ": "m_acc",
            "jti": access_jti,
            "exp": access_exp,
            "iat": now
        }
        
        refresh_payload = {
            "sid": staff_id,
            "env": env_hash,
            "typ": "m_ref",
            "jti": refresh_jti,
            "exp": refresh_exp,
            "iat": now
        }

        access_token = jwt.encode(access_payload, MANAGEMENT_SECRET, algorithm=ALGORITHM)
        refresh_token = jwt.encode(refresh_payload, MANAGEMENT_SECRET, algorithm=ALGORITHM)

        # =====================================================================
        # LAYER 2 & 4: JTI REGISTRATION & TOKEN FAMILY TRACKING
        # =====================================================================
        try:
            # 1. Register the Access Token (For the Kill-Switch)
            await valkey_client.setex(
                f"MGT_ACC_JTI:{access_jti}", 
                timedelta(minutes=15), 
                staff_id
            )
            
            # 2. Register the "Token Family" for Strict RTR
            # We track the LATEST valid refresh token for this specific device.
            family_key = f"MGT_FAMILY:{staff_id}:{env_hash}"
            await valkey_client.setex(
                family_key, 
                timedelta(days=7), 
                refresh_jti
            )
        except Exception as e:
            logger.error(f"[VALKEY FATAL] Failed to register tokens: {e}")
            raise RuntimeError("Internal Security Infrastructure Offline.")

        return access_token, refresh_token

    @classmethod
    async def rotate_refresh_token(cls, old_refresh_token: str, current_ip: str, current_ua: str) -> tuple[str, str]:
        """
        Executes Strict Refresh Token Rotation (RTR).
        Detects Replay Attacks and enforces Environmental Pinning.
        """
        try:
            payload = jwt.decode(old_refresh_token, MANAGEMENT_SECRET, algorithms=[ALGORITHM])
        except JWTError:
            raise ValueError("Cryptographic verification failed.")

        # Ensure it's actually a refresh token
        if payload.get("typ") != "m_ref":
            raise ValueError("Invalid token architecture.")

        staff_id = payload.get("sid")
        old_jti = payload.get("jti")
        token_env = payload.get("env")

        # Verify Environmental Pin (Has their IP/Browser changed?)
        current_env = cls._generate_env_fingerprint(current_ip, current_ua)
        if token_env != current_env:
            # The token was moved to a different machine/IP. Terminate immediately.
            raise ValueError("Environment mismatch. Session compromised.")

        # =====================================================================
        # REPLAY ATTACK DETECTION (The Brutal Execution)
        # =====================================================================
        family_key = f"MGT_FAMILY:{staff_id}:{current_env}"
        latest_valid_jti = await valkey_client.get(family_key)

        if not latest_valid_jti:
            raise ValueError("Session expired or manually terminated.")

        if old_jti != latest_valid_jti:
            # THE REPLAY ATTACK TRAP: 
            # The token is cryptographically valid, BUT it is not the latest one.
            # This means an attacker stole an old token and is trying to use it.
            # Response: NUKE THE ENTIRE FAMILY.
            await valkey_client.delete(family_key)
            logger.warning(f"SECURITY BREACH MITIGATED: Replay attack detected for staff {staff_id}. Session nuked.")
            raise ValueError("Security violation detected. All sessions revoked.")

        # If everything is valid, generate a brand new pair.
        # This automatically overwrites the `latest_valid_jti` in Valkey, 
        # instantly rendering the `old_refresh_token` dead.
        return await cls.issue_token_pair(staff_id, current_ip, current_ua)

    @classmethod
    async def verify_access_token(cls, token: str, current_ip: str, current_ua: str) -> str:
        """
        Verifies the short-lived access token for protected queries.
        """
        try:
            payload = jwt.decode(token, MANAGEMENT_SECRET, algorithms=[ALGORITHM])
        except JWTError:
            raise ValueError("Invalid credentials.")

        if payload.get("typ") != "m_acc":
            raise ValueError("Invalid token architecture.")

        # Verify Environment
        if payload.get("env") != cls._generate_env_fingerprint(current_ip, current_ua):
            raise ValueError("Environment mismatch.")

        # Verify Kill-Switch (Is the JTI still valid in Valkey?)
        jti = payload.get("jti")
        is_active = await valkey_client.exists(f"MGT_ACC_JTI:{jti}")
        if not is_active:
            raise ValueError("Session manually revoked.")

        return payload.get("sid")