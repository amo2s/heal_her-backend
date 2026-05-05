import strawberry
from typing import Optional, List
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

# Adjust import to match your project structure
from kids.videos.models import KidVideoProgress

logger = logging.getLogger("HEAL_SECURITY")

# =====================================================================
# THE OUTPUT CONTRACT (Zero-Leakage Entity Masking)
# =====================================================================
@strawberry.type
class KidVideoType:
    """
    The strict GraphQL contract for the Next.js frontend.
    Whatever is NOT in this class will never reach the internet, 
    even if the database row has 50 other columns.
    """
    # Force ID to be an immutable string to prevent integer-guessing attacks
    id: strawberry.ID 
    
    title: str
    topic: str
    duration: str
    thumbnail_url: str
    video_url: str
    
    # Optional field: Only fetched from DB when "Low Data Mode" is active
    transcript: Optional[str] = strawberry.field(
        description="Text fallback for Low Data Mode and Heal Buddy TTS."
    )

    # -----------------------------------------------------------------
    # THE SHADOW RESOLVER (The Progress Wall)
    # -----------------------------------------------------------------
    @strawberry.field(description="Dynamically resolves the user's secure watch progress.")
    async def watched(self, info: strawberry.Info) -> int:
        """
        Instead of returning a static database column, this lazy resolver 
        fires an isolated query using ONLY the verified JWT identity.
        The frontend cannot spoof whose progress it wants to see.
        """
        # 1. EXTRACT SECURE CONTEXT (Injected by IsKidAuthorized Guard)
        user_id = info.context.get("user_id")
        user_role = info.context.get("user_role")

        # 2. THE FAILSAFE TRAP
        # If the context is missing, or a non-kid slipped through, 
        # we return 0 and log a severe data leak prevention warning.
        if not user_id or user_role != "kid":
            logger.critical(f"[DATA LEAK TRAP] Unauthorized identity tried to resolve progress for video {self.id}")
            return 0

        # 3. EXTRACT DB SESSION
        db: AsyncSession = info.context.get("session")
        if not db:
            logger.error("[SYSTEM ERROR] Database session missing from GraphQL context.")
            return 0

        # 4. THE ATOMIC LOOKUP
        try:
            # Query the isolated KidVideoProgress table
            query = select(KidVideoProgress.watched_percentage).where(
                KidVideoProgress.user_id == user_id,
                KidVideoProgress.video_id == str(self.id)
            )
            result = await db.execute(query)
            percentage = result.scalar_one_or_none()
            
            # Return exact percentage, or 0 if they've never watched it
            return percentage if percentage is not None else 0
            
        except Exception as e:
            logger.error(f"[DB RESOLVER ERROR] Failed to fetch progress: {str(e)}")
            return 0


# =====================================================================
# THE WRAPPERS (Pagination & Safe Responses)
# =====================================================================
@strawberry.type
class KidVideoListResponse:
    """
    Prevents array-hijacking by wrapping lists in a strict response object.
    Includes metadata for pagination without exposing DB internals.
    """
    videos: List[KidVideoType]
    total_count: int


@strawberry.type
class KidVideoProgressResponse:
    """
    The response sent back to the video player after a heartbeat (progress update).
    """
    success: bool
    video_id: strawberry.ID
    updated_percentage: int
    message: str