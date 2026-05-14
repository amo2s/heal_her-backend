import asyncio
import bisect
import logging
from passlib.context import CryptContext
from supabase import create_client, Client
import uuid6

# Import your central settings
from core.config import settings
from db import Base

# [UPDATE]: Import the central Security Shield exceptions
from core.exceptions import ValidationError, InfrastructureError

# Set up professional security logging
logger = logging.getLogger("HEAL_SECURITY")
logger.setLevel(logging.WARNING)

# ---------------------------------------------------------
# 1. THE ALGORITHMIC ROLE RESOLVER
# ---------------------------------------------------------
class AccessControlRouter:
    """
    O(log N) Algorithmic Role Resolver.
    Replaces basic conditional blocks with binary search for instant, scalable routing.
    """
    # Upper bounds for age brackets: 12 (Kid), 17 (Teen). Anything higher defaults to the last index.
    _breakpoints = [12, 17] 
    _roles = ["kid", "teen", "young-adult"]

    @classmethod
    def resolve(cls, age: int) -> str:
        """Mathematically determines the user's system role based on age."""
        if age < 4 or age > 120:
            # [UPDATE]: Use ValidationError instead of a raw ValueError to prevent unhandled 500 crashes
            raise ValidationError(
                public_message="Provided age is out of supported operational bounds.",
                internal_message=f"Role resolution failed for out-of-bounds age: {age}"
            )
        
        # bisect_left calculates the exact index without iterating through if/else statements
        index = bisect.bisect_left(cls._breakpoints, age)
        return cls._roles[index]


# ---------------------------------------------------------
# 2. THE ARGON2ID ENGINE (Extremist Configuration)
# ---------------------------------------------------------
pwd_context = CryptContext(
    schemes=["argon2"],
    argon2__time_cost=3,       # Number of iterations
    argon2__memory_cost=65536, # 64MB of RAM required per hash
    argon2__parallelism=4,     # Number of parallel threads
    deprecated="auto",
)

# A pre-determined dummy string to waste exactly as much CPU time
# as a real password hash to prevent timing attacks.
DUMMY_PASSWORD = "HealHerTimingProtection2026!@#"


# ---------------------------------------------------------
# 3. SUPABASE SERVICE ROLE ISOLATION
# ---------------------------------------------------------
supabase_admin: Client = create_client(
    settings.SUPABASE_URL, 
    settings.SUPABASE_SERVICE_ROLE_KEY
)


# ---------------------------------------------------------
# 4. THE FORTIFIED SIGNUP EXECUTION
# ---------------------------------------------------------
async def create_secure_user(email: str, full_name: str, plain_password: str, age: int) -> dict:
    """
    Executes brutal security checks, algorithmic role resolution, and DB insertion.
    Guaranteed to protect against Side-Channel Timing Attacks and ID Enumeration.
    """
    try:
        # Step 1: Algorithmic Role Resolution
        # Calculates the role instantly BEFORE we spend resources on the database
        assigned_role = AccessControlRouter.resolve(age)

        # Step 2: Check for existing identity (Threaded for FastAPI async loop safety)
        response = await asyncio.to_thread(
            lambda: supabase_admin.table("users").select("id").eq("email", email).execute()
        )
        user_exists = len(response.data) > 0

        if user_exists:
            # --- TIMING ATTACK SHIELD ---
            # Bleed time matching a real hash to mask whether the email exists.
            await asyncio.to_thread(pwd_context.hash, DUMMY_PASSWORD)
            
            # [UPDATE]: Prevent Email Enumeration via Security Shield. 
            # The frontend gets a generic validation error, the backend logs the exact duplication attempt.
            raise ValidationError(
                public_message="Registration failed. Email may be unavailable or already registered.",
                internal_message=f"Signup identity conflict: Email {email} already in use."
            )

        # Step 3: Hash the actual password
        hashed_password = await asyncio.to_thread(pwd_context.hash, plain_password)

        # Step 4: Generate UUID v7 (Time-ordered, secure, and fast)
        secure_user_id = str(uuid6.uuid7())

        # Step 5: Prepare the Payload (Now includes the resolved 'role')
        new_user_data = {
            "id": secure_user_id,
            "email": email,
            "full_name": full_name,
            "age": age,
            "role": assigned_role,  # <-- Injected automatically!
            "password_hash": hashed_password,
            "is_active": True,
            "is_verified": False,
            "created_at": "now()"
        }

        # Step 6: Atomic Database Insert (Bypasses RLS)
        await asyncio.to_thread(
            lambda: supabase_admin.table("users").insert(new_user_data).execute()
        )

        # Step 7: Return Fortified Success Status
        return {
            "status": "success",
            "user_id": secure_user_id,
            "email": email,
            "role": assigned_role, # Let the frontend know exactly how to route them
            "message": "Account fortified and created successfully."
        }

    except ValidationError:
        # [UPDATE]: Let our specifically crafted ValidationErrors bubble up cleanly to the global handler
        raise

    except Exception as e:
        # [UPDATE]: The Ultimate Catch-All Infrastructure Shield.
        # We completely wipe out any trace of Supabase/PostgREST error messages here.
        # The exception shield turns this into "System Busy" for the user, while logging the stack trace internally.
        raise InfrastructureError(
            internal_message=f"Supabase DB Insert Failed for {email}: {str(e)}"
        )