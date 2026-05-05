import logging
from typing import Optional
from strawberry.types import Info
from graphql import GraphQLError
from pydantic import ValidationError

# Adjust imports to match your architecture
from kids.videos.schemas import KidVideoProgressUpdateSchema, KidVideoFilterSchema
from kids.videos.services import execute_progress_upsert, get_kid_videos_library
from kids.videos.types import KidVideoProgressResponse, KidVideoListResponse

logger = logging.getLogger("HEAL_SECURITY")

# =====================================================================
# THE WRITE ORCHESTRATOR (Progress Updates)
# =====================================================================
async def handle_update_kid_video_progress(
    info: Info, 
    video_id: str, 
    watched_percentage: int
) -> KidVideoProgressResponse:
    
    # 1. EXTRACT SECURE CONTEXT (Guaranteed by IsKidAuthorized)
    user_id = info.context.get("user_id")
    db = info.context.get("session")

    if not user_id or not db:
        logger.critical("[HANDLER FAULT] Execution attempted without secure context.")
        raise GraphQLError("Internal Security Fault. Request Terminated.")

    # 2. TRIGGER THE PYDANTIC FIREWALL
    try:
        clean_payload = KidVideoProgressUpdateSchema(
            video_id=video_id,
            watched_percentage=watched_percentage
        )
    except ValidationError as e:
        # If the frontend sends a bad UUID or watched % is 105, it dies here.
        logger.warning(f"[HANDLER FIREWALL] Malformed data rejected from {user_id}. Error: {e.errors()[0]['msg']}")
        raise GraphQLError("Validation Error: Invalid payload provided.")

    # 3. DELEGATE TO THE SERVICE CHAMBER
    try:
        final_percentage = await execute_progress_upsert(
            db=db,
            user_id=user_id,
            payload=clean_payload
        )
        
        # 4. MAP TO SAFE OUTPUT TYPE
        return KidVideoProgressResponse(
            success=True,
            video_id=video_id,
            updated_percentage=final_percentage,
            message="Progress secured."
        )
        
    except ValueError as ve:
        # Expected business logic errors (e.g., video doesn't exist)
        raise GraphQLError(str(ve))
    except Exception as e:
        # Catch and bury critical DB crashes. Never expose SQL errors to the frontend.
        logger.error(f"[HANDLER CRASH] {str(e)}")
        raise GraphQLError("An internal error occurred while processing your request.")


# =====================================================================
# THE READ ORCHESTRATOR (Fetching Library)
# =====================================================================
async def handle_get_kid_videos(
    info: Info, 
    topic: Optional[str], 
    search_query: Optional[str], 
    limit: int
) -> KidVideoListResponse:
    
    db = info.context.get("session")
    if not db:
        raise GraphQLError("Database connection failed.")

    # 1. TRIGGER THE PYDANTIC FIREWALL FOR SEARCH FILTERS
    try:
        clean_filters = KidVideoFilterSchema(
            topic=topic,
            search_query=search_query,
            limit=limit
        )
    except ValidationError as e:
        raise GraphQLError(f"Invalid search parameters: {e.errors()[0]['msg']}")

    # 2. DELEGATE TO SERVICE
    try:
        videos = await get_kid_videos_library(db=db, filters=clean_filters)
        
        # 3. MAP TO SAFE OUTPUT TYPE
        return KidVideoListResponse(
            videos=videos,
            total_count=len(videos) # Or you can add a separate count query in services if needed
        )
    except Exception as e:
        logger.error(f"[HANDLER CRASH] Failed to fetch library: {str(e)}")
        raise GraphQLError("Failed to load video library.")