"""
src/terms/services/auth_service.py

Handles the cryptographic generation, atomic caching, and strict verification 
of temporary Document Signature One-Time Passcodes (OTPs) using Aiven Valkey (Redis).
"""

import secrets
import logging
import redis.asyncio as redis

# Import central settings to match your existing pattern
from core.config import settings

# Custom Exception Shielding
class OTPVerificationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

# Set up professional security logging
logger = logging.getLogger("HEAL_LEGAL_SECURITY")
logger.setLevel(logging.WARNING)

# ---------------------------------------------------------
# CACHE CONFIGURATION (Synchronized with existing pattern)
# ---------------------------------------------------------
# Connect using the global REDIS_URL. decode_responses=True makes string retrieval seamless.
valkey_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# Strict 5-minute Time-To-Live (in seconds)
OTP_EXPIRATION_SECONDS = 300 

async def generate_and_cache_signature_otp(email: str) -> str:
    """
    Generates a cryptographically secure 6-digit OTP and caches it atomically.
    
    Returns:
        str: The raw 6-digit OTP to be emailed to the user.
    """
    # 1. Cryptographic Generation
    # secrets.choice ensures non-deterministic randomness pulling from OS entropy.
    # We strictly enforce 6 characters, allowing leading zeros (e.g., '049123')
    otp_code = ''.join(secrets.choice("0123456789") for _ in range(6))
    
    cache_key = f"tos_signature_otp:{email.lower().strip()}"
    
    # 2. Atomic Valkey Storage
    try:
        # SET with ex=300 atomically sets the value and the expiration in one round-trip.
        await valkey_client.set(name=cache_key, value=otp_code, ex=OTP_EXPIRATION_SECONDS)
        logger.info(f"Signature OTP successfully cached for {email}")
        return otp_code
    except redis.RedisError as e:
        logger.error(f"[INFRASTRUCTURE SHIELD] Valkey connection failed during OTP generation: {str(e)}")
        raise OTPVerificationError("Temporary system unavailability. Please try again later.")


async def verify_signature_otp(email: str, provided_otp: str) -> bool:
    """
    Retrieves and validates the OTP using constant-time comparison to prevent timing attacks.
    Automatically burns (deletes) the OTP upon successful verification.
    
    Returns:
        bool: True if verified, raises Exception if failed.
    """
    # Normalize inputs
    clean_email = email.lower().strip()
    clean_provided_otp = provided_otp.strip()
    cache_key = f"tos_signature_otp:{clean_email}"
    
    try:
        # 1. Retrieve from Cache
        stored_otp = await valkey_client.get(cache_key)
        
        if not stored_otp:
            logger.warning(f"Failed OTP verification: Expired or non-existent key for {clean_email}")
            raise OTPVerificationError("Verification code has expired or is invalid. Please request a new one.")
            
        # 2. Constant-Time Cryptographic Comparison
        # Prevents side-channel timing attacks by ensuring the comparison 
        # takes the exact same amount of microseconds regardless of input accuracy.
        is_valid = secrets.compare_digest(stored_otp, clean_provided_otp)
        
        if not is_valid:
            logger.warning(f"Failed OTP verification: Incorrect code provided for {clean_email}")
            raise OTPVerificationError("Incorrect verification code.")
            
        # 3. The Burn Protocol
        # If successful, immediately delete the OTP so it cannot be reused (replay attack prevention).
        await valkey_client.delete(cache_key)
        logger.info(f"OTP successfully verified and burned for {clean_email}")
        
        return True
        
    except redis.RedisError as e:
        logger.error(f"[INFRASTRUCTURE SHIELD] Valkey connection failed during OTP verification: {str(e)}")
        raise OTPVerificationError("Temporary system unavailability during verification.")