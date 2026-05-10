"""
src/kids/dashboard/resolvers.py

The Smart GraphQL Resolvers for the Kids Dashboard.
Calculates temporal context and atomizes user data to provide a personalized, child-friendly experience.
"""

import logging
from datetime import datetime
import strawberry
from strawberry.types import Info
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

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
        # 2. THE SILENT FAIL PERIMETER
        # =====================================================================
        if not db or not user_context:
            logger.warning("[DASHBOARD ANOMALY] get_me executed without complete context.")
            return KidIdentityResponse(
                success=False,
                message="Session invalidated or context breached."
            )
            
        # =====================================================================
        # 3. DATABASE HYDRATION
        # =====================================================================
        # The JWT only holds the ID. We must query the DB for the full name.
        user_id = user_context.get("sub")
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        current_user = result.scalars().first()

        if not current_user:
            return KidIdentityResponse(
                success=False,
                message="User profile not found in database."
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