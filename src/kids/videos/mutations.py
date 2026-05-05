import strawberry
from strawberry.types import Info

# Adjust imports to match your project structure
from kids.videos.handlers import handle_update_kid_video_progress
from kids.videos.guards import IsKidAuthorized
from kids.videos.types import KidVideoProgressResponse

# =====================================================================
# THE WRITE GATE (State-Change Interface)
# =====================================================================
@strawberry.type
class KidVideoMutation:
    """
    The strict GraphQL interface for modifying Kid Video data.
    Contains ZERO business logic. It solely defines the API surface,
    enforces the Triple-Lock Guard, and delegates to the Orchestrator.
    """

    @strawberry.mutation(permission_classes=[IsKidAuthorized])
    async def update_kid_video_progress(
        self, 
        info: Info, 
        video_id: str, 
        watched_percentage: int
    ) -> KidVideoProgressResponse:
        """
        Heartbeat mutation. Sent by the React player to save progress.
        Completely locked down by the Triple-Lock Guard before execution.
        """
        # Air-Gapped Delegation: We pass the raw arguments directly to the Orchestrator.
        # The Handler will force these inputs through the Pydantic Firewall 
        # (KidVideoProgressUpdateSchema) before the database is ever touched.
        return await handle_update_kid_video_progress(
            info=info, 
            video_id=video_id, 
            watched_percentage=watched_percentage
        )