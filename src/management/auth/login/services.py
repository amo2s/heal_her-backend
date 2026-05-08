import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from passlib.context import CryptContext

# Perimeter & Brain Imports
from management.auth.signup.models import Staff 
from management.auth.login.schemas import (
    AdminLoginInput, 
    StaffLoginInternal, 
    AdminLoginResponse, 
    StaffUserType,
    AdminRefreshResponse # [NEW]: Imported for the Refresh Door
)
from management.auth.login.utils import TokenForge

logger = logging.getLogger(__name__)

# =====================================================================
# THE CRYPTOGRAPHIC ENGINE (Argon2id)
# =====================================================================
# We explicitly force Argon2id. It resists both GPU cracking and side-channel 
# memory attacks. We disable all legacy algorithms.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# THE PHANTOM HASH: 
# Pre-computed hash of a non-existent password. Used to equalize CPU time 
# when an account doesn't exist, completely destroying timing-enumeration attacks.
DUMMY_HASH = pwd_context.hash("phantom_password_123!@#_DO_NOT_USE")


class StaffLoginService:
    """
    The Extremist Authentication Brain.
    Executes Status-Blind Verification, Timing Attack Neutralization, 
    and handles the deployment of the Ghost Protocol.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_login_interrogation(
        self, 
        input_data: AdminLoginInput, 
        security_intel: dict
    ) -> AdminLoginResponse:
        """
        The core verification sequence. Never trust the input.
        Never reveal internal state.
        """
        # 1. Extract Intelligence from Guards
        is_ghost = security_intel.get("is_ghost", False)
        true_ip = security_intel.get("true_ip", "0.0.0.0")
        user_agent = security_intel.get("user_agent", "unknown")

        # =====================================================================
        # 2. CONSTANT-TIME DATABASE LATENCY
        # =====================================================================
        # Whether this is a ghost bot or a real user, we ALWAYS query the database.
        # If we skipped the DB for bots, an attacker could measure the latency 
        # difference to figure out they've been ghosted.
        stmt = select(Staff).where(Staff.email == input_data.email)
        result = await self.db.execute(stmt)
        staff = result.scalar_one_or_none()

        # =====================================================================
        # 3. THE GHOST PROTOCOL (Execution)
        # =====================================================================
        if is_ghost:
            # We spend CPU cycles hashing the dummy password to match normal latency
            pwd_context.verify(input_data.password, DUMMY_HASH)
            logger.warning(f"[GHOST TRAP TRIGGERED] Neutralized attack vector for IP: {true_ip}")
            # Hand them the fake tokens and send them to the void
            return AdminLoginResponse.generate_ghost_response()

        # =====================================================================
        # 4. TIMING EQUALIZATION (The Phantom Hash)
        # =====================================================================
        if not staff:
            # The email does not exist.
            # We hash the dummy password anyway to burn the exact same amount of 
            # CPU time as a real login. The attacker learns nothing.
            pwd_context.verify(input_data.password, DUMMY_HASH)
            raise ValueError("Invalid credentials.")

        # =====================================================================
        # 5. THE INTERROGATION (Constant-Time Verification)
        # =====================================================================
        valid_password = pwd_context.verify(input_data.password, staff.hashed_password)
        if not valid_password:
            raise ValueError("Invalid credentials.")

        # =====================================================================
        # 6. STATUS-BLIND VERIFICATION
        # =====================================================================
        # If the account is PENDING approval or manually SUSPENDED by the Admin.
        # We do NOT tell the user "Your account is suspended." 
        # We give them the exact same generic error. Zero information leaked.
        staff_status = getattr(staff.status, "name", str(staff.status)).upper()
        if staff_status != "ACTIVE":
            logger.warning(f"[UNAUTHORIZED ACCESS ATTEMPT] {staff.email} attempted login while {staff_status}.")
            raise ValueError("Invalid credentials.")

        # =====================================================================
        # 7. ATOMIC AUDIT LOGGING & ANOMALY DETECTION
        # =====================================================================
        # We track physical movement. If the IP changes radically from signup, log it.
        if staff.signup_ip and staff.signup_ip != true_ip:
            logger.info(f"[ANOMALY] Staff {staff.id} login from new IP: {true_ip}. Original: {staff.signup_ip}")

        staff.last_login_at = datetime.now(timezone.utc)
        await self.db.commit()

        # =====================================================================
        # 8. INTERNAL AIR-GAP PROJECTION
        # =====================================================================
        # Map the raw SQLAlchemy object into the strict Pydantic DTO.
        # This severs all ORM ties and ensures hashed passwords don't leak to memory.
        staff_role = getattr(staff.role, "name", str(staff.role)).upper()
        
        internal_user = StaffLoginInternal(
            id=str(staff.id),
            email=staff.email,
            full_name=staff.full_name,
            role=staff_role,
            status=staff_status
        )

        # =====================================================================
        # 9. TOKEN FORGE (Blood-Binding)
        # =====================================================================
        access_token, refresh_token = await TokenForge.issue_token_pair(
            staff_id=internal_user.id,
            ip=true_ip,
            user_agent=user_agent
        )

        # =====================================================================
        # 10. EGRESS FORMATTING
        # =====================================================================
        # Return perfectly formatted response matching the Next.js proxy contract.
        return AdminLoginResponse(
            status="success",
            message="Authorized. Redirecting to Management Dashboard...",
            accessToken=access_token,
            refreshToken=refresh_token,
            user=StaffUserType(
                id=internal_user.id,
                email=internal_user.email,
                fullName=internal_user.full_name,
                isActive=True,
                dashboard="management" # Hard-enforced routing matching frontend expectations
            )
        )


    # =====================================================================
    # [NEW] 11. THE REFRESH AIR-LOCK
    # =====================================================================
    async def refresh_staff_session(
        self, 
        old_refresh_token: str, 
        current_ip: str, 
        current_ua: str
    ) -> AdminRefreshResponse:
        """
        The secondary perimeter. Executes Blood-Bound Token Rotation and 
        verifies the staff member's clearance has not been revoked.
        """
        # A. Trigger the Cryptographic Rotation (Valkey Checks, Replay Mitigation)
        # If the environment mismatched or it's a replay attack, this will throw an error 
        # and immediately halt execution.
        new_access, new_refresh = await TokenForge.rotate_refresh_token(
            old_refresh_token=old_refresh_token,
            current_ip=current_ip,
            current_ua=current_ua
        )

        # B. We must extract the Staff ID from the payload to verify their status.
        # Since TokenForge already verified the cryptographic signature, it is safe to 
        # blindly decode the old token here just to get the ID.
        import jwt as pyjwt # Safe local import to avoid modifying top-level dependencies
        from core.config import settings
        
        payload = pyjwt.decode(
            old_refresh_token, 
            settings.MANAGEMENT_JWT_SECRET_KEY, 
            algorithms=["HS256"]
        )
        
        # [FIX] Read from "sub" instead of "sid" to match the TokenForge output
        staff_id = payload.get("sub")

        # C. VERIFICATION OF CLEARANCE (Status-Blind Check)
        # Even if the token is valid, we must ensure an Admin didn't manually 
        # suspend this user 5 minutes ago.
        stmt = select(Staff).where(Staff.id == staff_id)
        result = await self.db.execute(stmt)
        staff = result.scalar_one_or_none()

        if not staff:
            logger.error(f"[PHANTOM SESSION DETECTED] Valid token used for non-existent staff ID: {staff_id}")
            raise ValueError("Invalid credentials.")

        staff_status = getattr(staff.status, "name", str(staff.status)).upper()
        if staff_status != "ACTIVE":
            logger.warning(f"[SUSPENDED ACCESS ATTEMPT] {staff.email} attempted token refresh while {staff_status}.")
            raise ValueError("Invalid credentials.")

        # D. ATOMIC AUDIT LOGGING
        # We log the successful refresh to keep a tight audit trail.
        staff.last_login_at = datetime.now(timezone.utc)
        await self.db.commit()

        # E. THE STERILE EGRESS
        return AdminRefreshResponse(
            accessToken=new_access,
            refreshToken=new_refresh
        )