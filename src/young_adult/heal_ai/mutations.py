"""
src/young_adult/heal_ai/graphql/mutations.py

Administrative actions for Young Adult Heal AI.
Provides renaming, soft-deleting, and bulk purging of session history.
"""

import strawberry
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

# Import the young_adult-specific models
from young_adult.heal_ai.models import YoungAdultChatSession

# [FIXED]: Import the shared type from our new isolated Type Registry
from young_adult.heal_ai.types import YoungAdultChatSessionType

# ---------------------------------------------------------
# 1. GRAPHQL RETURN TYPES (PAYLOAD PATTERN)
# ---------------------------------------------------------
@strawberry.type
class YoungAdultDeleteSessionPayload:
    success: bool
    message: str
    deleted_session_id: Optional[str]

@strawberry.type
class YoungAdultClearHistoryPayload:
    success: bool
    message: str
    sessions_cleared_count: int


# ---------------------------------------------------------
# 2. THE MUTATIONS CLASS
# ---------------------------------------------------------
@strawberry.type
class HealAIMutations:
    
    @strawberry.mutation
    async def rename_chat_session(
        self, 
        info: strawberry.Info, 
        session_id: str, 
        new_title: str
    ) -> YoungAdultChatSessionType:
        """
        Allows the user to manually rename a specific Heal AI session.
        """
        db: AsyncSession = info.context["db"]
        
        # Identity Extraction: Aligning with the bulletproof sub/user_id check
        user_context = info.context.get("user_context", {})
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
        
        if not user_id:
            raise Exception("Unauthorized: Identity verification failed.")

        # Scoped fetch: Ensure the session belongs to the authenticated young adult
        result = await db.execute(
            select(YoungAdultChatSession)
            .where(YoungAdultChatSession.id == session_id, YoungAdultChatSession.user_id == user_id)
        )
        session_record = result.scalars().first()

        if not session_record:
            raise Exception("Session not found or permission denied.")

        # Update and Commit
        session_record.title = new_title[:100]  # Respect database constraints
        await db.commit()
        await db.refresh(session_record)

        return YoungAdultChatSessionType(
            id=session_record.id,
            user_id=session_record.user_id,
            title=session_record.title,
            is_deleted=session_record.is_deleted,
            created_at=str(session_record.created_at),
            updated_at=str(session_record.updated_at)
        )

    @strawberry.mutation
    async def delete_chat_session(
        self, 
        info: strawberry.Info, 
        session_id: str
    ) -> YoungAdultDeleteSessionPayload:
        """
        Soft-deletes a session. It remains in DB for safety/audit but is removed from UI.
        """
        db: AsyncSession = info.context["db"]
        user_context = info.context.get("user_context", {})
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
        
        if not user_id:
            return YoungAdultDeleteSessionPayload(success=False, message="Unauthorized.", deleted_session_id=None)

        # Atomic Soft Delete
        query = (
            update(YoungAdultChatSession)
            .where(YoungAdultChatSession.id == session_id, YoungAdultChatSession.user_id == user_id)
            .values(is_deleted=True)
            .execution_options(synchronize_session=False)
        )
        
        result = await db.execute(query)
        await db.commit()

        if result.rowcount == 0:
            return YoungAdultDeleteSessionPayload(
                success=False, 
                message="Session not found or already archived.", 
                deleted_session_id=None
            )

        return YoungAdultDeleteSessionPayload(
            success=True, 
            message="Session archived successfully.", 
            deleted_session_id=session_id
        )

    @strawberry.mutation
    async def clear_all_chat_history(self, info: strawberry.Info) -> YoungAdultClearHistoryPayload:
        """
        Performs a bulk soft-delete of all active sessions for the current young adult.
        """
        db: AsyncSession = info.context["db"]
        user_context = info.context.get("user_context", {})
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
        
        if not user_id:
            return YoungAdultClearHistoryPayload(success=False, message="Unauthorized.", sessions_cleared_count=0)

        # Bulk Atomic Soft Delete
        query = (
            update(YoungAdultChatSession)
            .where(YoungAdultChatSession.user_id == user_id, YoungAdultChatSession.is_deleted == False)
            .values(is_deleted=True)
            .execution_options(synchronize_session=False)
        )
        
        result = await db.execute(query)
        await db.commit()

        return YoungAdultClearHistoryPayload(
            success=True, 
            message="Heal AI history cleared successfully.", 
            sessions_cleared_count=result.rowcount
        )