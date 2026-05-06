import logging
import strawberry
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from core.config import settings

# Perimeter & Brain Imports
from management.auth.login.guards import LoginBouncerGuard
# [NEW]: Added AdminRefreshResponse to the schema imports
from management.auth.login.schemas import AdminLoginInput, AdminLoginResponse, AdminRefreshResponse
from management.auth.login.services import StaffLoginService

logger = logging.getLogger(__name__)

@strawberry.type
class AdminLoginMutation:
    """
    The Master Entry Point for Management Authentication.
    Directly wired to the Next.js Proxy contract.
    """

    @strawberry.mutation(permission_classes=[LoginBouncerGuard])
    async def admin_login(
        self, 
        info: strawberry.types.Info, 
        input_data: AdminLoginInput
    ) -> AdminLoginResponse:
        """
        The Master Resolver. 
        Orchestrates the transition from public request to internal session.
        """
        # =====================================================================
        # 1. THE SESSION SIPHON
        # =====================================================================
        # Extract the database session from the global GraphQL context.
        db: AsyncSession = info.context.get("db")
        if not db:
            logger.error("[SYSTEM FATAL] Database session missing from GraphQL context.")
            raise Exception("Authentication Service Unavailable.")
        
        # =====================================================================
        # 2. INTEL EXTRACTION (Guard Symbiosis)
        # =====================================================================
        # Retrieve the behavioral analysis performed by the LoginBouncerGuard.
        security_intel = info.context.get("security_intel", {
            "true_ip": "0.0.0.0",
            "user_agent": "unknown",
            "is_ghost": True  
        })

        try:
            # =====================================================================
            # 3. STRUCTURAL VALIDATION (The Air-Lock)
            # =====================================================================
            sanitized_input = input_data.validate_and_sanitize()

            # =====================================================================
            # 4. SERVICE ACTIVATION (The Brain)
            # =====================================================================
            service = StaffLoginService(db)
            
            response = await service.execute_login_interrogation(
                input_data=sanitized_input,
                security_intel=security_intel
            )

            return response

        except ValueError as ve:
            # =====================================================================
            # 5. THE STERILIZATION CHAMBER (Generic Error Masking)
            # =====================================================================
            logger.warning(
                f"[AUTH REJECTED] {str(ve)} | Target: {input_data.email} | IP: {security_intel.get('true_ip')}"
            )
            raise Exception("Invalid administrative credentials.")

        except Exception as e:
            # =====================================================================
            # 6. CRITICAL SYSTEM FAILURE
            # =====================================================================
            logger.error(f"[CRITICAL AUTH FAILURE] {str(e)}", exc_info=True)
            raise Exception("Authentication Service Unavailable.")


    # =====================================================================
    # [NEW] THE REFRESH DOOR: BLOOD-BOUND ROTATION
    # =====================================================================
    @strawberry.mutation
    async def admin_refresh_token(
        self,
        info: strawberry.types.Info,
        refresh_token: str
    ) -> AdminRefreshResponse:
        """
        Executes Extremist Refresh Token Rotation.
        Enforces the Cryptographic Handshake and extracts intel for Environmental Pinning.
        """
        # =====================================================================
        # 1. THE HANDSHAKE SENTINEL (Perimeter Defense)
        # =====================================================================
        request: Request = info.context.get("request")
        if not request:
            logger.error("[SYSTEM FATAL] HTTP Request missing from GraphQL context.")
            raise Exception("Authentication Service Unavailable.")

        client_handshake = request.headers.get("x-healher-handshake")
        if not client_handshake or client_handshake != settings.FRONTEND_HANDSHAKE_SECRET:
            logger.warning("[SECURITY BREACH] Handshake bypass attempted on Refresh Door.")
            raise Exception("Security Violation: Invalid Client Signature.")

        # =====================================================================
        # 2. THE SESSION SIPHON
        # =====================================================================
        db: AsyncSession = info.context.get("db")
        if not db:
            raise Exception("Authentication Service Unavailable.")

        # =====================================================================
        # 3. AUDIT INTEL EXTRACTION (For Blood-Binding)
        # =====================================================================
        # Extract the precise IP and User-Agent needed by the TokenForge to 
        # verify if the user's environment has changed.
        forwarded_for = request.headers.get("x-forwarded-for")
        current_ip = forwarded_for.split(',')[0].strip() if forwarded_for else "127.0.0.1"
        current_ua = request.headers.get("user-agent", "unknown")

        try:
            # =====================================================================
            # 4. DELEGATION TO THE BRAIN
            # =====================================================================
            service = StaffLoginService(db)
            
            response = await service.refresh_staff_session(
                old_refresh_token=refresh_token,
                current_ip=current_ip,
                current_ua=current_ua
            )
            return response

        except ValueError as ve:
            # =====================================================================
            # 5. THE STERILIZATION CHAMBER (Masking Replay Attacks)
            # =====================================================================
            # Whether it's an IP mismatch, an expired token, or an active Replay Attack,
            # we return the exact same generic error.
            logger.warning(f"[REFRESH REJECTED] {str(ve)} | IP: {current_ip}")
            raise Exception("Invalid or expired session.")

        except Exception as e:
            # =====================================================================
            # 6. CRITICAL SYSTEM FAILURE
            # =====================================================================
            logger.error(f"[CRITICAL REFRESH FAILURE] {str(e)}", exc_info=True)
            raise Exception("Authentication Service Unavailable.")