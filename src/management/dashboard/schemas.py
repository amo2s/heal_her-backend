import strawberry
from typing import Optional

# =====================================================================
# 1. THE IDENTITY PILLAR (Read-Only UI Data)
# =====================================================================
@strawberry.type
class StaffProfileType:
    """
    The Minimalist Passport. 
    Exposes ONLY what the Next.js Topbar and Greeting animation need.
    Zero internal UUIDs, Zero timestamps, Zero database logic.
    """
    full_name: str
    role: str 
    email: str  # Included just in case you want to show it in the Topbar Profile Dropdown

# =====================================================================
# 2. THE SUCCESS WRAPPER (Data Contract)
# =====================================================================
@strawberry.type
class StaffIdentityResponse:
    """
    The GraphQL Response Payload for the `getMe` query.
    If the context is breached or missing, success = False and profile remains None.
    """
    success: bool
    profile: Optional[StaffProfileType] = None
    message: Optional[str] = None