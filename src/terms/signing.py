"""
src/terms/signing.py

Intent layer: binds a specific consent payload to a specific verified OTP window.
The payload locked here is the ONLY copy of "what was agreed to" the system trusts later.
"""

import hmac
import json
import hashlib
import logging

from core.config import settings
from terms.auth_service import valkey_client, OTP_EXPIRATION_SECONDS

logger = logging.getLogger("HEAL_LEGAL_SECURITY")

# Locked payload dies with its OTP — a payload should never outlive the code that unlocks it.
CONSENT_PAYLOAD_TTL_SECONDS = OTP_EXPIRATION_SECONDS


class ConsentPayloadError(Exception):
    """Raised when a locked payload is missing, expired, corrupted, or fails integrity checks."""
    pass


def _hash_email(email: str) -> str:
    """Local copy of the log-safe email fingerprint — trivial, kept file-local on purpose."""
    return hashlib.sha256(email.encode()).hexdigest()[:12]


def _sign(serialized: str) -> str:
    """HMAC-SHA256 over the exact serialized payload, keyed by a server-only secret."""
    return hmac.new(
        settings.CONSENT_SIGNING_SECRET.encode(), serialized.encode(), hashlib.sha256
    ).hexdigest()


async def lock_consent_payload(email: str, payload: dict) -> None:
    """
    Serializes and HMAC-signs the payload, then caches the signed envelope
    under the same email key the OTP flow uses, with an identical expiry.
    """
    clean_email = email.lower().strip()
    email_fp = _hash_email(clean_email)

    # sort_keys makes serialization deterministic — same payload always signs identically.
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    envelope = json.dumps({"data": serialized, "sig": _sign(serialized)})

    await valkey_client.set(f"consent_payload:{clean_email}", envelope, ex=CONSENT_PAYLOAD_TTL_SECONDS)
    logger.info(f"Consent payload locked for {email_fp}")


async def release_consent_payload(email: str) -> dict:
    """
    Retrieves the locked payload, verifies its HMAC, and deletes it — one-time release only.
    Must only be called AFTER verify_signature_otp has already burned the matching OTP.
    """
    clean_email = email.lower().strip()
    email_fp = _hash_email(clean_email)
    key = f"consent_payload:{clean_email}"

    raw_envelope = await valkey_client.get(key)
    if not raw_envelope:
        logger.warning(f"Consent release failed: no locked payload for {email_fp}")
        raise ConsentPayloadError("No locked consent payload found for this session.")

    # Delete immediately regardless of outcome below — a payload is used at most once, ever.
    await valkey_client.delete(key)

    try:
        envelope = json.loads(raw_envelope)
        serialized = envelope["data"]
        provided_sig = envelope["sig"]
    except (KeyError, json.JSONDecodeError):
        logger.critical(f"[INTEGRITY SHIELD] Corrupted consent envelope for {email_fp}")
        raise ConsentPayloadError("Consent payload was corrupted and could not be trusted.")

    # Constant-time comparison — this is the tamper check, not just a format check.
    expected_sig = _sign(serialized)
    if not hmac.compare_digest(expected_sig, provided_sig):
        logger.critical(f"[INTEGRITY SHIELD] HMAC mismatch on consent payload for {email_fp}")
        raise ConsentPayloadError("Consent payload integrity check failed.")

    logger.info(f"Consent payload released for {email_fp}")
    return json.loads(serialized)