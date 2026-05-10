"""
src/kids/dashboard/queries.py

The Central Query Hub for the Kids Dashboard.
Aggregates identity, content, and activity modules into a single GraphQL entry point.
"""

import strawberry
from typing import List, Optional

# [IMPORT UPGRADES]: Importing the specialized query modules for the Kids sector
from kids.dashboard.resolvers import KidDashboardQueries

# Placeholder imports for your future modules
# from kids.videos.queries import VideoQueries
# from kids.ai_buddy.queries import AIBuddyQueries

@strawberry.type
class KidsDashboardQuery(KidDashboardQueries):
    """
    The Unified Read-Only Layer.
    Inherits get_me from KidDashboardQueries and expands into other domains.
    """

    @strawberry.field
    async def dashboard_health(self) -> str:
        """Simple heartbeat for the Kids sector."""
        return "Kids Dashboard Data Layer is operational."

    # [FUTURE EXPANSION]: Example of how you will mount the video module
    # @strawberry.field
    # async def videos(self, info) -> List[VideoType]:
    #     return await VideoQueries.get_featured_videos(info)

    # [FUTURE EXPANSION]: Example of how you will mount AI history
    # @strawberry.field
    # async def ai_history(self, info) -> List[ChatSessionType]:
    #     return await AIBuddyQueries.get_recent_sessions(info)