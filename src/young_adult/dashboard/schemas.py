"""
src/young_adult/dashboard/schemas.py

The Smart GraphQL Schema for the Young Adult Dashboard.
Separates core user identity from UI presentation logic to keep the Next.js frontend fast and "dumb".
"""

import strawberry
from typing import Optional

# =====================================================================
# 1. THE IDENTITY PILLAR (Who the user is)
# =====================================================================
@strawberry.type
class YoungAdultProfileType:
    """
    The Minimalist Passport for Young Adults.
    [REFACTORED]: Extracted from the shared identity architecture.
    """
    # [FEATURE MAINTAINED]: first_name allows for peer-level, professional personalization
    first_name: str 
    full_name: str
    role: str 
    email: str


# =====================================================================
# 2. THE PRESENTATION PILLAR (How the UI feels)
# =====================================================================
@strawberry.type
class YoungAdultDashboardContext:
    """
    The Vibe Engine - Young Adult Edition.
    [ARCHITECTURAL UPGRADE]: Offloads computation of greetings and engagement 
    states to the backend for a consistent multi-platform experience.
    """
    # [FEATURE MAINTAINED]: Dynamically calculated (e.g., "Good Morning", "Hello")
    greeting: str 
    
    # [FEATURE MAINTAINED]: A supportive message tailored for adult users 
    # (e.g., "How is your self-care journey going?")
    contextual_message: str 
    
    # [FEATURE MAINTAINED]: Tracking engagement and consistency
    current_streak: Optional[int] = 0 


# =====================================================================
# 3. THE SUCCESS WRAPPER (Data Contract)
# =====================================================================
@strawberry.type
class YoungAdultIdentityResponse:
    """
    The GraphQL Response Payload for the Young Adult `getMe` query.
    [ARCHITECTURAL UPGRADE]: Maintains strict separation between static profile 
    data and dynamic UI context.
    """
    success: bool
    
    # The pure user data
    profile: Optional[YoungAdultProfileType] = None
    
    # The smart UI metadata injected alongside the profile
    context: Optional[YoungAdultDashboardContext] = None 
    
    message: Optional[str] = None