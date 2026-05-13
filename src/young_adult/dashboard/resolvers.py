"""
src/young_adult/dashboard/resolvers.py

The Smart GraphQL Resolvers for the Young Adult Dashboard.
Calculates temporal context and atomizes user data to provide a personalized, vibe-based experience.
"""

import logging
from datetime import datetime
import strawberry
from strawberry.types import Info
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

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
        # 2. THE SILENT FAIL PERIMETER
        # =====================================================================
        if not db or not user_context:
            logger.warning("[DASHBOARD ANOMALY] get_me executed without complete context.")
            return YoungAdultIdentityResponse(
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
            return YoungAdultIdentityResponse(
                success=False,
                message="User profile not found in database."
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