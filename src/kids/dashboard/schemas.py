"""
src/kids/dashboard/schemas.py

The Smart GraphQL Schema for the Kids Dashboard.
Tailored for a simplified, high-engagement UI for younger users.
"""

import strawberry
from typing import Optional

# =====================================================================
# 1. THE IDENTITY PILLAR (Who the kid is)
# =====================================================================
@strawberry.type
class KidProfileType:
    """
    The Minimalist Passport for Kids.
    [REFACTORED]: Adapted from the Teen/Staff structures for demographic isolation.
    """
    # [FEATURE MAINTAINED]: first_name is critical for peer-level AI interaction
    first_name: str 
    full_name: str
    role: str 
    email: str


# =====================================================================
# 2. THE PRESENTATION PILLAR (How the UI feels)
# =====================================================================
@strawberry.type
class KidDashboardContext:
    """
    The Vibe Engine - Kids Edition.
    [ARCHITECTURAL UPGRADE]: Encapsulates all temporal and engagement logic 
    to keep the frontend implementation clean.
    """
    # [FEATURE MAINTAINED]: Calculated by the Kids resolver (e.g., "Good Morning")
    greeting: str 
    
    # [FEATURE MAINTAINED]: A supportive, child-friendly subtitle 
    # (e.g., "Ready to talk to your AI Buddy?")
    contextual_message: str 
    
    # [FEATURE MAINTAINED]: Streak tracking to encourage daily wellness habits
    current_streak: Optional[int] = 0 


# =====================================================================
# 3. THE SUCCESS WRAPPER (Data Contract)
# =====================================================================
@strawberry.type
class KidIdentityResponse:
    """
    The GraphQL Response Payload for the Kids `getMe` query.
    [ARCHITECTURAL UPGRADE]: Strictly isolates identity from dashboard-specific context.
    """
    success: bool
    
    # The pure user data
    profile: Optional[KidProfileType] = None
    
    # The smart UI metadata injected specifically for the Kids dashboard
    context: Optional[KidDashboardContext] = None 
    
    message: Optional[str] = None