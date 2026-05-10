"""
src/teens/dashboard/mutations.py

The Central Action Hub for the Teens Dashboard.
Handles all state-changing operations (Writes) for the teen demographic.
"""

import strawberry
from strawberry.types import Info # [FIXED]: Imported Info for type annotation
from typing import Optional

# [FUTURE IMPORTS]: These will be added as you build the modules
# from teens.wellness.mutations import WellnessMutations
# from teens.profile.mutations import ProfileUpdateMutations

@strawberry.type
class TeensDashboardMutation:
    """
    The Unified Action Layer.
    All dashboard-specific writes (updates, deletions, creations) are routed here.
    """

    @strawberry.mutation
    async def track_dashboard_visit(self, info: Info) -> bool: # [FIXED]: Added : Info annotation
        """
        [FEATURE LOGIC]: A background mutation to track engagement 
        and update the login_streak used by the resolver.
        """
        user_context = info.context.get("user_context")
        if not user_context:
            return False
            
        # Logic for incrementing current_user.login_streak in the DB
        return True

    # [FUTURE EXPANSION]: Example of mounting profile updates
    # @strawberry.mutation
    # async def update_teen_profile(self, info: Info, input: UpdateInput) -> UpdateResponse:
    #     return await ProfileUpdateMutations.execute(input)