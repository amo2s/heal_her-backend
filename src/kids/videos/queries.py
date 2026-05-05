import strawberry
from typing import Optional

# Adjust imports to match your project structure
from kids.videos.handlers import handle_get_kid_videos
from kids.videos.guards import IsKidAuthorized
from kids.videos.types import KidVideoListResponse

# =====================================================================
# THE READ GATE (Query Interface)
# =====================================================================
@strawberry.type
class KidVideoQuery:
    """
    The strict GraphQL interface for reading Kid Video data.
    Contains ZERO business logic. It solely defines the API surface 
    and enforces the Triple-Lock Guard before delegation.
    """

    @strawberry.field(permission_classes=[IsKidAuthorized])
    async def kid_videos(
        self, 
        info: strawberry.Info, 
        topic: Optional[str] = None, 
        search_query: Optional[str] = None, 
        limit: int = 20
    ) -> KidVideoListResponse:
        """
        Fetches the video library for the Kids dashboard.
        Protected by IsKidAuthorized. The underlying lazy resolvers 
        in KidVideoType will securely calculate the active user's progress.
        """
        # Immediately hand off to the Orchestrator
        return await handle_get_kid_videos(
            info=info, 
            topic=topic, 
            search_query=search_query, 
            limit=limit
        )