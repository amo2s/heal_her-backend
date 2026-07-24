"""
src/terms/auth_service.py

Identity verification layer: cryptographic generation, atomic caching, rate-limited
and lockout-protected verification of Document Signature OTPs via Aiven Valkey (Redis).
"""

import hashlib
import secrets
import logging
import redis.asyncio as redis

from core.config import settings

# --- EXCEPTIONS ---
class OTPVerificationError(Exception):
    """Raised for any failed, expired, rate-limited, or locked-out OTP flow."""
    def __init__(self, message: str, retry_after_seconds: int | None = None):
        self.message = message
        # Lets the GraphQL layer surface a "try again in N seconds" hint to the client.
        self.retry_after_seconds = retry_after_seconds
        super().__init__(self.message)


logger = logging.getLogger("HEAL_LEGAL_SECURITY")
logger.setLevel(logging.WARNING)

valkey_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# --- POLICY CONSTANTS (OWASP Authentication Cheat Sheet aligned) ---
OTP_EXPIRATION_SECONDS = 300        # 5-minute validity window per issued OTP.
GENERATION_COOLDOWN_SECONDS = 60    # Minimum gap between OTP sends to stop email/SMS-bombing.
MAX_ATTEMPTS_PER_OTP = 5            # Wrong guesses allowed before this OTP is burned + locked.
CUMULATIVE_FAIL_WINDOW_SECONDS = 86400   # 24h rolling window for aggregate abuse tracking.
CUMULATIVE_FAIL_LIMIT = 10          # Total daily failures before an extended, manual-review lock.
LOCKOUT_BASE_SECONDS = 30           # Starting lockout duration; doubles per escalation.
LOCKOUT_MAX_ESCALATIONS = 4         # Caps exponential growth so a lock can't run forever silently.
LOCKOUT_MANUAL_REVIEW_SECONDS = 3600  # Hard 1-hour lock once cumulative daily limit is hit.


def _hash_email(email: str) -> str:
    """Returns a truncated SHA-256 fingerprint so raw emails never touch logs/telemetry."""
    return hashlib.sha256(email.encode()).hexdigest()[:12]


def _normalize(email: str) -> str:
    """Single source of truth for email normalization, reused by every key below."""
    return email.lower().strip()


async def _get_lockout_remaining(email: str) -> int | None:
    """Returns seconds left on an active lockout, or None if the account isn't locked."""
    ttl = await valkey_client.ttl(f"otp_lockout:{email}")
    # Redis returns -2 (no key) or -1 (no expiry) for a missing lock; both mean "not locked".
    return ttl if ttl and ttl > 0 else None


async def _apply_lockout(email: str) -> int:
    """Escalating exponential lockout: doubles each time, capped, then forces a long manual-review lock."""
    escalation_key = f"otp_lockout_escalations:{email}"
    escalations = await valkey_client.incr(escalation_key)
    if escalations == 1:
        # First escalation in this 24h cycle; anchor the counter's own expiry.
        await valkey_client.expire(escalation_key, CUMULATIVE_FAIL_WINDOW_SECONDS)

    if escalations > LOCKOUT_MAX_ESCALATIONS:
        duration = LOCKOUT_MANUAL_REVIEW_SECONDS
    else:
        duration = LOCKOUT_BASE_SECONDS * (2 ** (escalations - 1))

    await valkey_client.set(f"otp_lockout:{email}", "1", ex=duration)
    return duration


async def generate_and_cache_signature_otp(email: str) -> str:
    """
    Generates a cryptographically secure 6-digit OTP and caches it atomically.
    Enforces a send-cooldown and respects any active lockout before issuing a new code.
    """
    clean_email = _normalize(email)
    email_fp = _hash_email(clean_email)

    try:
        locked_for = await _get_lockout_remaining(clean_email)
        if locked_for:
            logger.warning(f"OTP generation blocked: account locked for {email_fp}")
            raise OTPVerificationError(
                "Too many failed attempts. Please try again later.", retry_after_seconds=locked_for
            )

        cooldown_key = f"otp_gen_cooldown:{clean_email}"
        # NX ensures we only set the cooldown if it doesn't already exist — a cheap, atomic guard.
        cooldown_set = await valkey_client.set(cooldown_key, "1", ex=GENERATION_COOLDOWN_SECONDS, nx=True)
        if not cooldown_set:
            remaining = await valkey_client.ttl(cooldown_key)
            logger.warning(f"OTP generation rate-limited for {email_fp}")
            raise OTPVerificationError(
                "Please wait before requesting another code.", retry_after_seconds=remaining
            )

        otp_code = ''.join(secrets.choice("0123456789") for _ in range(6))
        cache_key = f"tos_signature_otp:{clean_email}"

        await valkey_client.set(name=cache_key, value=otp_code, ex=OTP_EXPIRATION_SECONDS)
        # Fresh OTP means fresh attempt budget for it specifically.
        await valkey_client.delete(f"otp_verify_attempts:{clean_email}")

        logger.info(f"Signature OTP successfully cached for {email_fp}")
        return otp_code

    except redis.RedisError as e:
        logger.error(f"[INFRASTRUCTURE SHIELD] Valkey failure during OTP generation ({email_fp}): {str(e)}")
        raise OTPVerificationError("Temporary system unavailability. Please try again later.")


async def verify_signature_otp(email: str, provided_otp: str) -> bool:
    """
    Validates the OTP with constant-time comparison, enforces per-OTP and
    daily-aggregate attempt limits, and burns the code on success or exhaustion.
    """
    clean_email = _normalize(email)
    clean_provided_otp = provided_otp.strip()
    email_fp = _hash_email(clean_email)
    cache_key = f"tos_signature_otp:{clean_email}"
    attempts_key = f"otp_verify_attempts:{clean_email}"
    cumulative_key = f"otp_cumulative_fail:{clean_email}"

    try:
        locked_for = await _get_lockout_remaining(clean_email)
        if locked_for:
            logger.warning(f"Verification blocked: account locked for {email_fp}")
            raise OTPVerificationError(
                "Too many failed attempts. Please try again later.", retry_after_seconds=locked_for
            )

        stored_otp = await valkey_client.get(cache_key)
        if not stored_otp:
            logger.warning(f"Failed OTP verification: expired or non-existent key for {email_fp}")
            raise OTPVerificationError("Verification code has expired or is invalid. Please request a new one.")

        is_valid = secrets.compare_digest(stored_otp, clean_provided_otp)

        if not is_valid:
            # Pipeline keeps the two counter updates atomic against concurrent requests.
            pipe = valkey_client.pipeline()
            pipe.incr(attempts_key)
            pipe.expire(attempts_key, OTP_EXPIRATION_SECONDS)
            pipe.incr(cumulative_key)
            pipe.expire(cumulative_key, CUMULATIVE_FAIL_WINDOW_SECONDS)
            attempt_count, _, cumulative_count, _ = await pipe.execute()

            logger.warning(f"Failed OTP verification attempt {attempt_count} for {email_fp}")

            if int(cumulative_count) >= CUMULATIVE_FAIL_LIMIT:
                await valkey_client.delete(cache_key)
                await valkey_client.set(f"otp_lockout:{clean_email}", "1", ex=LOCKOUT_MANUAL_REVIEW_SECONDS)
                logger.error(f"Daily failure ceiling hit — manual-review lock applied for {email_fp}")
                raise OTPVerificationError(
                    "Account temporarily locked for review.", retry_after_seconds=LOCKOUT_MANUAL_REVIEW_SECONDS
                )

            if int(attempt_count) >= MAX_ATTEMPTS_PER_OTP:
                await valkey_client.delete(cache_key)
                duration = await _apply_lockout(clean_email)
                logger.error(f"Max attempts exceeded — OTP burned and locked for {email_fp}")
                raise OTPVerificationError(
                    "Too many incorrect attempts. Please try again later.", retry_after_seconds=duration
                )

            raise OTPVerificationError("Incorrect verification code.")

        # Success: burn the OTP and clear the per-OTP attempt counter (replay prevention).
        await valkey_client.delete(cache_key, attempts_key)
        logger.info(f"OTP successfully verified and burned for {email_fp}")

        return True

    except redis.RedisError as e:
        logger.error(f"[INFRASTRUCTURE SHIELD] Valkey failure during OTP verification ({email_fp}): {str(e)}")
        raise OTPVerificationError("Temporary system unavailability during verification.")