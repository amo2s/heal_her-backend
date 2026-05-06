from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from fastapi import Request
from passlib.context import CryptContext

from core.config import settings
from .models import Staff, StaffRole, StaffStatus
from .schemas import StaffSignUpInput, StaffSignUpResponse

# =====================================================================
# CRYPTOGRAPHIC ENGINE
# =====================================================================
# We use Argon2id, configured with high memory/CPU requirements 
# to make brute-force attacks mathematically unfeasible.
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__time_cost=3, 
    argon2__memory_cost=65536,
    argon2__parallelism=4
)

class StaffAuthService:
    """
    The Fortress Gateway. Handles registration and authentication logic
    with extreme prejudice against bots and reconnaissance attacks.
    """

    @staticmethod
    async def create_pending_staff(
        db: AsyncSession, 
        request: Request, 
        payload: StaffSignUpInput
    ) -> StaffSignUpResponse:
        
        # 1. THE TARPIT (Bot Neutralization)
        # If the hidden 'website' field contains anything, a bot filled it out.
        if payload.website:
            return StaffSignUpResponse()

        # 2. ANTI-ENUMERATION RECONNAISSANCE (Upgraded to Async 2.0 Syntax)
        stmt = select(Staff).where(Staff.email == payload.email)
        result = await db.execute(stmt)
        existing_staff = result.scalars().first()

        if existing_staff:
            # The email already exists. We will NEVER give an attacker that information.
            # THE GHOST HASH (Timing Attack Shield):
            _ = pwd_context.hash(payload.password)
            return StaffSignUpResponse()

        # 3. CRYPTOGRAPHIC ENFORCEMENT
        hashed_pwd = pwd_context.hash(payload.password)

        # 4. AUDIT TRAIL METADATA EXTRACTION
        client_ip = request.client.host if request.client else None
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
            
        user_agent = request.headers.get("User-Agent")

        # 5. ZERO-TRUST DEPLOYMENT
        new_staff = Staff(
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hashed_pwd,
            role=StaffRole.PENDING_STAFF,  # LOCKED: Zero Privileges
            status=StaffStatus.PENDING,    # LOCKED: Cannot Authenticate
            signup_ip=client_ip,
            signup_user_agent=user_agent
        )

        # 6. ASYNC DATABASE INJECTION & INTEGRITY CHECK
        try:
            db.add(new_staff)
            await db.commit()
        except SQLAlchemyError as e:
            # The transaction failed (e.g., Supabase dropped connection, constraint failed)
            await db.rollback()
            print(f"[FATAL DB WRITE ERROR]: {str(e)}") 
            
            # We override the default "Success=True" to alert the frontend
            return StaffSignUpResponse(
                success=False,
                message="Service temporarily unavailable. Could not provision credentials."
            )

        # 7. THE MIRROR RESPONSE
        return StaffSignUpResponse()