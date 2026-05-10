"""
src/teens/dashboard/schemas.py

The Smart GraphQL Schema for the Teens Dashboard.
Separates core user identity from UI presentation logic to keep the Next.js frontend fast and "dumb".
"""

import strawberry
from typing import Optional

# =====================================================================
# 1. THE IDENTITY PILLAR (Who the user is)
# =====================================================================
@strawberry.type
class TeenProfileType:
    """
    The Minimalist Passport for Teens.
    [REFACTORED]: Extracted from the old StaffProfileType.
    """
    # [FEATURE ADDED]: first_name added to allow "Hey Alex" instead of "Hello Alex Doe"
    first_name: str 
    full_name: str
    role: str 
    email: str


# =====================================================================
# 2. THE PRESENTATION PILLAR (How the UI feels)
# =====================================================================
@strawberry.type
class TeenDashboardContext:
    """
    The Vibe Engine.
    [ARCHITECTURAL UPGRADE]: This entirely new type prevents the Next.js frontend 
    from having to calculate timezones, greetings, or user activity states. 
    The backend computes the "vibe" and sends it ready-to-render.
    """
    # [FEATURE ADDED]: Dynamically calculated by the resolver (e.g., "Good Morning", "Good Evening")
    greeting: str 
    
    # [FEATURE ADDED]: A supportive, vibe-based subtitle (e.g., "Ready for your session?" or "Taking some time for yourself?")
    contextual_message: str 
    
    # [FEATURE ADDED]: Gamification/Engagement metric to encourage return visits
    current_streak: Optional[int] = 0 


# =====================================================================
# 3. THE SUCCESS WRAPPER (Data Contract)
# =====================================================================
@strawberry.type
class TeenIdentityResponse:
    """
    The GraphQL Response Payload for the Teen `getMe` query.
    [ARCHITECTURAL UPGRADE]: Now strictly separates pure profile data from the dashboard UI context.
    """
    success: bool
    
    # The pure user data
    profile: Optional[TeenProfileType] = None
    
    # [FEATURE ADDED]: The smart UI metadata injected alongside the profile
    context: Optional[TeenDashboardContext] = None 
    
    message: Optional[str] = None