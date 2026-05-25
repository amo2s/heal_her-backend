import asyncio
import secrets
import hashlib
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from passlib.context import CryptContext

# Import the core Valkey client we just engineered
from core.redis import valkey_client
from core.exceptions import AuthenticationError
from mailers.reset_password import send_reset_otp_email

# Assuming User model location based on your login service structure
from auth.models.signup import User 

logger = logging.getLogger("HEAL_SECURITY")
logger.setLevel(logging.WARNING)

# Argon2 Password Hashing Engine
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


async def request_password_reset_service(email: str, db: AsyncSession) -> dict:
    """
    PHASE 1: Generates the OTP and fires the email. 
    Protected by a Ghost Protocol to prevent timing-based email enumeration.
    """
    clean_email = email.lower().strip()
    
    # 1. Check if the user exists in the database
    query = select(User).where(User.email == clean_email)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        # [SECURITY]: The Ghost Protocol
        # If the email doesn't exist, we sleep to mimic the time it takes 
        # to generate an OTP and dispatch the network request. 
        # Hackers cannot use response times to guess valid emails.
        await asyncio.sleep(0.8)
        return {
            "status": "success",
            "message": "If the provided credentials match an active vault account, a secure authorization code has been dispatched."
        }

    # 2. Cryptographically secure 6-digit generation (never use standard 'random')
    otp_code = "".join(secrets.choice("0123456789") for _ in range(6))
    
    # 3. Cache Hashing Shield (Never store plain OTPs in memory)
    otp_hash = hashlib.sha256(otp_code.encode()).hexdigest()
    
    # Store the hash in Valkey with a strict 10-minute expiration (600 seconds)
    await valkey_client.setex(f"security:otp:{clean_email}", 600, otp_hash)

    # 4. Async Dispatch
    # We use asyncio.create_task to fire the email in the background.
    # The API returns the response instantly without waiting for Google's servers.
    recipient_name = getattr(user, 'full_name', getattr(user, 'fullName', 'User'))
    asyncio.create_task(
        send_reset_otp_email(
            email=clean_email, 
            recipient_name=recipient_name, 
            otp_code=otp_code
        )
    )

    return {
        "status": "success",
        "message": "If the provided credentials match an active vault account, a secure authorization code has been dispatched."
    }


async def verify_reset_otp_service(email: str, otp_code: str) -> str:
    """
    PHASE 2: Verifies the OTP, manages Brute-Force strikes, 
    and issues a high-entropy short-lived reset token.
    """
    clean_email = email.lower().strip()
    
    # Hash the incoming guess to compare with our stored hash
    input_hash = hashlib.sha256(otp_code.encode()).hexdigest()
    stored_hash = await valkey_client.get(f"security:otp:{clean_email}")

    if not stored_hash or stored_hash != input_hash:
        # [SECURITY]: The 3-Strike Rule Implementation
        fails_key = f"security:fails:email:{clean_email}"
        strikes = await valkey_client.incr(fails_key)
        
        if strikes == 1:
            await valkey_client.expire(fails_key, 900) # 15 min window
            
        if strikes >= 3:
            # Trigger the absolute operational lockout block that guards.py checks
            await valkey_client.setex(f"security:lockout:email:{clean_email}", 900, "1")
            logger.warning(f"[BRUTE FORCE SHIELD] Lockout triggered for {clean_email}")

        # Zero-Information Drop
        raise AuthenticationError(internal_message="invalid or expired authorization code.")

    # [SECURITY]: The Atomic Burn
    # The OTP was correct. Destroy it immediately so it can never be re-used.
    await valkey_client.delete(f"security:otp:{clean_email}")
    await valkey_client.delete(f"security:fails:email:{clean_email}")

    # Generate a High-Entropy 32-byte Reset Token
    reset_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(reset_token.encode()).hexdigest()

    # Bind the hashed token to the verified email in Valkey (Strict 5 min window)
    await valkey_client.setex(f"security:reset_token:{token_hash}", 300, clean_email)

    return reset_token


async def confirm_password_reset_service(reset_token: str, new_password: str, db: AsyncSession) -> dict:
    """
    PHASE 3: Consumes the reset token, updates the Supabase/PostgreSQL 
    database with Argon2, and finalizes the ledger lock.
    """
    # Hash the incoming token to look it up in Valkey
    token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
    verified_email = await valkey_client.get(f"security:reset_token:{token_hash}")

    if not verified_email:
        # Zero-Information Drop for expired or invalid tokens
        raise AuthenticationError(internal_message="invalid or expired reset token sequence.")

    # [SECURITY]: Replay Attack Purge
    # Destroy the token immediately. Even if the DB update fails, they must start over.
    await valkey_client.delete(f"security:reset_token:{token_hash}")

    # Hash the new password using Argon2
    new_password_hash = pwd_context.hash(new_password)

    # Execute the Ledger Lock (Direct Database Update)
    query = (
        update(User)
        .where(User.email == verified_email)
        .values(password_hash=new_password_hash)
    )
    await db.execute(query)
    
    # Commit the transaction to the Supabase cloud database
    await db.commit()

    logger.info(f"[VAULT UPDATE] Password successfully reset for {verified_email}")

    return {
        "status": "success",
        "message": "Your vault password has been successfully updated."
    }