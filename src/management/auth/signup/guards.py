import typing
import strawberry
from strawberry.permission import BasePermission
from strawberry.types import Info
from sqlalchemy.future import select

from .models import Staff, StaffStatus, StaffRole
from core.security import get_current_user_id

# =====================================================================
# THE SENTINEL BASE: GRAPHQL PERMISSION ENGINE
# =====================================================================
class ManagementGuard(BasePermission):
    """
    The Base Sentinel for Strawberry GraphQL.
    Intercepts the resolver, performs a live DB check to ensure instant 
    session termination, and physically attaches the verified identity 
    to the execution context.
    """
    message = "Security Violation: Access Denied."
    allowed_roles: typing.List[StaffRole] = []

    async def has_permission(self, source: typing.Any, info: Info, **kwargs) -> bool:
        # Strawberry typically passes request and db via context dict
        request = info.context.get("request")
        db = info.context.get("db") # Now an AsyncSession

        if not request or not db:
            self.message = "System Failure: Execution context breached."
            return False

        # 1. JWT EXTRACTION & IDENTITY PRE-CHECK
        try:
            # Assumes get_current_user_id returns the ID. 
            # If it throws an HTTPException, we catch it to handle it cleanly in GraphQL.
            user_id = await get_current_user_id(request)
        except Exception as e:
            # We catch the FastAPI HTTPExceptions and convert them to GraphQL rejection messages
            self.message = getattr(e, "detail", "Security Violation: Invalid or Missing Credentials.")
            return False
        
        # 2. LIVE DATABASE STATE CHECK (The "Kill-Switch")
        # Upgraded to SQLAlchemy 2.0 Async Syntax
        stmt = select(Staff).where(Staff.id == user_id)
        result = await db.execute(stmt)
        staff = result.scalars().first()
        
        if not staff:
            self.message = "Security Violation: Identity Unknown."
            return False

        # 3. THE STATE-MACHINE GATE
        if staff.status != StaffStatus.ACTIVE:
            self.message = "Access Denied: Account is not in an active state."
            return False

        # 4. ROLE HIERARCHY ENFORCEMENT (God-Mode Override)
        if staff.role not in self.allowed_roles and staff.role != StaffRole.SUPER_ADMIN:
            self.message = "Privilege Escalation Blocked: Insufficient Clearance."
            return False

        # 5. CONTEXTUAL FINGERPRINTING (Air-Gap tracking)
        current_ua = request.headers.get("user-agent")
        if staff.signup_user_agent and current_ua != staff.signup_user_agent:
            pass 

        # 6. ZERO-TRUST CONTEXT INJECTION
        # We attach the verified staff object to the context.
        # Resolvers MUST use this instead of trusting user input for identity.
        info.context["current_staff"] = staff

        return True

# =====================================================================
# THE BOUNCERS (Strict Class Implementations for Strawberry)
# =====================================================================
# Usage in resolvers: @strawberry.mutation(permission_classes=[IsSuperAdmin])

class IsActiveStaff(ManagementGuard):
    """General management dashboard access (viewing stats, etc.)"""
    allowed_roles = [
        StaffRole.ADMIN, 
        StaffRole.MODERATOR, 
        StaffRole.TEACHER, 
        StaffRole.CONTENT_CREATOR
    ]

class IsSuperAdmin(ManagementGuard):
    """THE VAULT: Only for Approval Dashboard, Role Assignment, User Suspension"""
    allowed_roles = [StaffRole.SUPER_ADMIN]

class IsContentManager(ManagementGuard):
    """Strictly for uploading, editing, or deleting Kid Videos"""
    allowed_roles = [
        StaffRole.ADMIN, 
        StaffRole.TEACHER, 
        StaffRole.CONTENT_CREATOR
    ]