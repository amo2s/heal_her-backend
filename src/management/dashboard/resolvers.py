import logging
import strawberry
from strawberry.types import Info

# Perimeter & Schema Imports
from management.auth.login.guards import IsActiveStaff
from .schemas import StaffIdentityResponse, StaffProfileType

logger = logging.getLogger(__name__)

@strawberry.type
class DashboardQuery:
    """
    The Command Center Read-Only Data Layer.
    All resolvers here must be gated by strict RBAC guards.
    """

    # Corrected: Strawberry uses @strawberry.field for queries
    @strawberry.field(permission_classes=[IsActiveStaff])
    async def get_me(self, info: Info) -> StaffIdentityResponse:
        """
        The Zero-Query Identity Siphon.
        Extracts the pre-verified Staff identity directly from the execution context.
        Executes in < 1ms because the database hit happened in the Guard.
        """
        # =====================================================================
        # 1. THE CONTEXT SIPHON
        # =====================================================================
        # The IsActiveStaff guard has already validated the JWT and queried the DB.
        # It physically attached the verified SQL user object to 'current_staff'.
        current_staff = info.context.get("current_staff")
        
        # =====================================================================
        # 2. THE SILENT FAIL PERIMETER
        # =====================================================================
        # If the guard logic fails to populate the context, we kill the response.
        if not current_staff:
            logger.warning("[DASHBOARD ANOMALY] get_me executed without current_staff in context.")
            return StaffIdentityResponse(
                success=False,
                message="Session invalidated or context breached."
            )
            
        # =====================================================================
        # 3. ENUM NORMALIZATION
        # =====================================================================
        # Normalize the SQLAlchemy Enum to a clean uppercase string for the frontend.
        role_str = getattr(current_staff.role, "name", str(current_staff.role)).upper()
        
        # =====================================================================
        # 4. THE AIR-GAPPED PROJECTION
        # =====================================================================
        # Mapping ONLY safe UI fields. PII and sensitive DB keys never leave the server.
        profile = StaffProfileType(
            full_name=current_staff.full_name,
            role=role_str,
            email=current_staff.email
        )
        
        # =====================================================================
        # 5. THE STERILE EGRESS
        # =====================================================================
        return StaffIdentityResponse(
            success=True,
            profile=profile,
            message="Identity verified."
        )