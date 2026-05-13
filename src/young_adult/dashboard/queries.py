"""
src/young_adult/dashboard/queries.py

The Central Query Hub for the Young Adult Dashboard.
Aggregates identity, content, and activity modules into a single GraphQL entry point.
"""

import strawberry
from typing import List, Optional

# [IMPORT UPGRADES]: Importing the specialized query modules for Young Adults
from young_adult.dashboard.resolvers import YoungAdultDashboardQueries

# Placeholder imports for your future modules
# from young_adult.videos.queries import VideoQueries
# from young_adult.heal_ai.queries import HealAIQueries

@strawberry.type
class YoungAdultDashboardQuery(YoungAdultDashboardQueries):
    """
    The Unified Read-Only Layer.
    Inherits get_me from YoungAdultDashboardQueries and expands into other domains.
    """

    @strawberry.field
    async def dashboard_health(self) -> str:
        """Simple heartbeat for the Young Adult sector."""
        return "Young Adult Dashboard Data Layer is operational."

    # [FUTURE EXPANSION]: Example of how you will mount the video module
    # @strawberry.field
    # async def videos(self, info) -> List[VideoType]:
    #     return await VideoQueries.get_featured_videos(info)

    # [FUTURE EXPANSION]: Example of how you will mount AI history
    # @strawberry.field
    # async def ai_history(self, info) -> List[ChatSessionType]:
    #     return await HealAIQueries.get_recent_sessions(info)