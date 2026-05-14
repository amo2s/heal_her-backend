"""
src/kids/dashboard/resolvers.py

The Smart GraphQL Resolvers for the Kids Dashboard.
Calculates temporal context and atomizes user data to provide a personalized, child-friendly experience.
Now fully integrated with the HEAL Security Shield and Adaptive Execution Engine.
"""

import logging
import inspect
from datetime import datetime
import strawberry
from strawberry.types import Info
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# [UPDATE]: Security Shield Integration
# We import AuthenticationError to drop unauthorized requests instantly via the global interceptor.
from core.exceptions import AuthenticationError

# [UPDATED IMPORT]: Fetching the central User model to retrieve full profile data
from auth.models.signup import User 

# [UPDATED IMPORTS]: Pulling in the Kids-specific upgraded schema structures
from .schemas import KidIdentityResponse, KidProfileType, KidDashboardContext

logger = logging.getLogger(__name__)

# =====================================================================
# UTILITY HELPER: THE TEMPORAL WARDEN (KIDS EDITION)
# =====================================================================
def get_temporal_vibe(hour: int) -> dict:
    """
    [FEATURE ADDED]: Dynamically generates the greeting and contextual message
    based on the server time (or user timezone) tailored for younger users.
    STRICT COMPLIANCE: Zero emojis used.
    """
    if 5 <= hour < 12:
        return {
            "greeting": "Good Morning",
            "message": "Ready to play and learn today?"
        }
    elif 12 <= hour < 17:
        return {
            "greeting": "Good Afternoon",
            "message": "Having a fun day so far?"
        }
    elif 17 <= hour < 20:
        return {
            "greeting": "Good Evening",
            "message": "Time to wind down and relax."
        }
    else:
        # Late night logic (stricter for kids)
        return {
            "greeting": "Hello",
            "message": "It is past bedtime! Make sure to get plenty of sleep."
        }


# =====================================================================
# THE RESOLVER LAYER
# =====================================================================
@strawberry.type
class KidDashboardQueries:
    """
    The Command Center Read-Only Data Layer for Kids.
    """

    @strawberry.field
    async def get_me(self, info: Info) -> KidIdentityResponse:
        """
        The Smart Identity Siphon.
        Extracts the JWT context, fetches the SQL user, and computes the dashboard vibe.
        """
        # =====================================================================
        # 1. THE CONTEXT SIPHON
        # =====================================================================
        # [ARCHITECTURAL UPGRADE]: We extract the db session and JWT payload 
        # injected by the kids router.py's get_graphql_context.
        db: AsyncSession = info.context.get("db")
        user_context = info.context.get("user_context")
        
        # =====================================================================
        # 2. THE SECURITY SHIELD PERIMETER
        # =====================================================================
        # [UPDATE]: Replaced silent "success=False" returns with loud internal AuthenticationErrors.
        if not db or not user_context:
            raise AuthenticationError(
                internal_message="[DASHBOARD ANOMALY] get_me executed without complete context."
            )
            
        # [UPDATE]: Standardized ID extraction mirroring the rest of the backend architecture.
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
        if not user_id:
            raise AuthenticationError(
                internal_message="[DASHBOARD ANOMALY] Missing user identity in context."
            )

        # =====================================================================
        # 3. DATABASE HYDRATION (Adaptive Execution)
        # =====================================================================
        # The JWT only holds the ID. We must query the DB for the full name.
        query = select(User).where(User.id == user_id)
        
        # [UPDATE]: Implemented the Adaptive Execution Engine to handle sync/async session states gracefully.
        execute_result = db.execute(query)
        if inspect.isawaitable(execute_result):
            result = await execute_result
        else:
            result = execute_result
            
        current_user = result.scalars().first()

        # [UPDATE]: If the user is missing from the DB (e.g., account deleted but token valid), 
        # we instantly revoke access via the global interceptor rather than returning a soft fail.
        if not current_user:
            raise AuthenticationError(
                internal_message=f"Orphaned Token: User profile {user_id} not found in database."
            )

        # =====================================================================
        # 4. NAME ATOMIZATION (First-Name-First Logic)
        # =====================================================================
        # [FEATURE ADDED]: Safely splits the full name to extract just the first name 
        # for a more personal, peer-level AI greeting.
        raw_full_name = getattr(current_user, 'full_name', getattr(current_user, 'fullName', 'User'))
        first_name = raw_full_name.split(" ")[0].capitalize() if raw_full_name else "There"

        # =====================================================================
        # 5. TEMPORAL VIBE COMPUTATION
        # =====================================================================
        # [ARCHITECTURAL UPGRADE]: Offloads UI logic from the frontend.
        current_hour = datetime.now().hour
        vibe_data = get_temporal_vibe(current_hour)

        # =====================================================================
        # 6. THE AIR-GAPPED PROJECTION
        # =====================================================================
        # Mapping Identity Data
        profile_data = KidProfileType(
            first_name=first_name,
            full_name=raw_full_name,
            role=user_context.get("role", "kid").upper(),
            email=current_user.email
        )
        
        # Mapping Presentation Data
        context_data = KidDashboardContext(
            greeting=vibe_data["greeting"],
            contextual_message=vibe_data["message"],
            current_streak=getattr(current_user, 'login_streak', 0) # Fallback to 0 if column doesn't exist yet
        )
        
        # =====================================================================
        # 7. THE STERILE EGRESS
        # =====================================================================
        return KidIdentityResponse(
            success=True,
            profile=profile_data,
            context=context_data,
            message="Identity verified and context generated."
        )