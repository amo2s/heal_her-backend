"""
src/young_adult/dashboard/resolvers.py

The Smart GraphQL Resolvers for the Young Adult Dashboard.
Calculates temporal context and atomizes user data to provide a personalized, vibe-based experience.
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
from core.exceptions import AuthenticationError

# [UPDATED IMPORT]: Fetching the central User model to retrieve full profile data
from auth.models.signup import User 

# [UPDATED IMPORTS]: Pulling in the newly upgraded schema structures for Young Adults
from .schemas import YoungAdultIdentityResponse, YoungAdultProfileType, YoungAdultDashboardContext

logger = logging.getLogger(__name__)

# =====================================================================
# UTILITY HELPER: THE TEMPORAL WARDEN
# =====================================================================
def get_temporal_vibe(hour: int) -> dict:
    """
    [FEATURE ADDED]: Dynamically generates the greeting and contextual message
    based on the server time (or user timezone), tailored for young adults.
    STRICT COMPLIANCE: Zero emojis used per system instructions.
    """
    if 5 <= hour < 12:
        return {
            "greeting": "Good Morning",
            "message": "Ready to tackle the day and prioritize your well-being?"
        }
    elif 12 <= hour < 17:
        return {
            "greeting": "Good Afternoon",
            "message": "Taking a midday break? Remember to breathe and recenter."
        }
    elif 17 <= hour < 22:
        return {
            "greeting": "Good Evening",
            "message": "Winding down? Let us reflect on your progress today."
        }
    else:
        # Late night logic
        return {
            "greeting": "Hello",
            "message": "Still up? Rest is a crucial part of your self-care journey."
        }


# =====================================================================
# THE RESOLVER LAYER
# =====================================================================
@strawberry.type
class YoungAdultDashboardQueries:
    """
    The Command Center Read-Only Data Layer for Young Adults.
    """

    @strawberry.field
    async def get_me(self, info: Info) -> YoungAdultIdentityResponse:
        """
        The Smart Identity Siphon.
        Extracts the JWT context, fetches the SQL user, and computes the dashboard vibe.
        """
        # =====================================================================
        # 1. THE CONTEXT SIPHON
        # =====================================================================
        # [ARCHITECTURAL UPGRADE]: We extract the db session and JWT payload 
        # injected by router.py's get_graphql_context.
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

        # [UPDATE]: If the user is missing from the DB, revoke access instantly.
        if not current_user:
            raise AuthenticationError(
                internal_message=f"Orphaned Token: Young Adult profile {user_id} not found in database."
            )

        # =====================================================================
        # 4. NAME ATOMIZATION (First-Name-First Logic)
        # =====================================================================
        # [FEATURE ADDED]: Safely splits the full name to extract just the first name 
        # for a more personal, peer-level greeting.
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
        profile_data = YoungAdultProfileType(
            first_name=first_name,
            full_name=raw_full_name,
            role=user_context.get("role", "young_adult").upper(),
            email=current_user.email
        )
        
        # Mapping Presentation Data
        context_data = YoungAdultDashboardContext(
            greeting=vibe_data["greeting"],
            contextual_message=vibe_data["message"],
            current_streak=getattr(current_user, 'login_streak', 0) # Fallback to 0 if column doesn't exist yet
        )
        
        # =====================================================================
        # 7. THE STERILE EGRESS
        # =====================================================================
        return YoungAdultIdentityResponse(
            success=True,
            profile=profile_data,
            context=context_data,
            message="Identity verified and context generated."
        )