import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

# Adjust imports to match your project structure
from kids.videos.models import KidVideo, KidVideoProgress
from kids.videos.schemas import KidVideoProgressUpdateSchema, KidVideoFilterSchema

logger = logging.getLogger("HEAL_SECURITY")

# =====================================================================
# THE EXECUTION CHAMBER (Pure Business Logic)
# =====================================================================

async def get_kid_videos_library(db: AsyncSession, filters: KidVideoFilterSchema) -> list[KidVideo]:
    """
    Safely retrieves the video library using the Pydantic firewall constraints.
    """
    query = select(KidVideo)

    # Apply strictly validated filters
    if filters.topic:
        query = query.where(KidVideo.topic == filters.topic)
    
    if filters.search_query:
        # Using ilike for case-insensitive search. Pydantic ensures search_query is safe.
        query = query.where(KidVideo.title.ilike(f"%{filters.search_query}%"))

    # Enforce the hard cap limit set by the schema
    query = query.limit(filters.limit)

    try:
        result = await db.execute(query)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"[SERVICE FAULT] Failed to fetch video library: {str(e)}")
        raise RuntimeError("Database execution failed during library retrieval.")


async def execute_progress_upsert(
    db: AsyncSession, 
    user_id: str, 
    payload: KidVideoProgressUpdateSchema
) -> int:
    """
    The heart of the progress system. Uses Atomic Row Locking and a One-Way Ratchet.
    """
    # ---------------------------------------------------------
    # STEP 1: THE PHANTOM BLOCKER (Referential Integrity Check)
    # ---------------------------------------------------------
    # We never trust the frontend's video_id, even if it's a valid UUID.
    # We must confirm the video actually exists in the kid_videos table.
    video_check_query = select(KidVideo.id).where(KidVideo.id == payload.video_id)
    video_exists = await db.execute(video_check_query)
    
    if not video_exists.scalar_one_or_none():
        logger.warning(f"[SERVICE BLOCK] User {user_id} attempted to update progress for a non-existent video: {payload.video_id}")
        raise ValueError("Invalid target: Video does not exist in the isolated library.")

    # ---------------------------------------------------------
    # STEP 2: THE ATOMIC LOCK (Preventing Race Conditions)
    # ---------------------------------------------------------
    # If a user double-clicks or a script spams the endpoint, two requests 
    # might hit the DB at the exact same millisecond. 
    # .with_for_update() places a physical lock on the row so only one transaction 
    # can touch it at a time.
    progress_query = select(KidVideoProgress).where(
        KidVideoProgress.user_id == user_id,
        KidVideoProgress.video_id == payload.video_id
    ).with_for_update()

    try:
        result = await db.execute(progress_query)
        progress_record = result.scalar_one_or_none()

        # ---------------------------------------------------------
        # STEP 3: THE ONE-WAY RATCHET
        # ---------------------------------------------------------
        if progress_record:
            # If the database says they are at 80%, and the payload says 20%, we ignore it.
            # Progress can mathematically only move FORWARD.
            if payload.watched_percentage > progress_record.watched_percentage:
                progress_record.watched_percentage = payload.watched_percentage
            else:
                logger.info(f"[SERVICE RATCHET] Blocked backward/duplicate progress for {user_id}. Attempted: {payload.watched_percentage}%, Kept: {progress_record.watched_percentage}%")
                
            # We return the DB's truth, not the payload's request
            final_percentage = progress_record.watched_percentage

        # ---------------------------------------------------------
        # STEP 4: THE SECURE INSERT
        # ---------------------------------------------------------
        else:
            # First time watching this video
            new_record = KidVideoProgress(
                user_id=user_id,
                video_id=payload.video_id,
                watched_percentage=payload.watched_percentage
            )
            db.add(new_record)
            final_percentage = payload.watched_percentage

        # Commit the transaction to release the row lock
        await db.commit()
        return final_percentage

    except IntegrityError as e:
        # Catches severe database constraint violations
        await db.rollback()
        logger.critical(f"[SERVICE FATAL] Integrity violation during upsert for {user_id}: {str(e)}")
        raise RuntimeError("Data integrity lock enforced. Update aborted.")
        
    except Exception as e:
        await db.rollback()
        logger.error(f"[SERVICE ERROR] Unhandled exception during upsert: {str(e)}")
        raise RuntimeError("Internal processing error.")