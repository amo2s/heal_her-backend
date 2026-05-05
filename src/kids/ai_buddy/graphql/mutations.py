"""
kids/ai_buddy/graphql/mutations.py

Handles the Administrative actions for the Kids AI Buddy (Renaming, Deleting, Purging).
Implements strict Context-Aware Security to prevent ID Spoofing and atomic soft-deletes.
"""

import strawberry
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

# Import your database models
from kids.ai_buddy.models import ChatSession

# ---------------------------------------------------------
# 1. GRAPHQL RETURN TYPES (PAYLOAD PATTERN)
# ---------------------------------------------------------
@strawberry.type
class ChatSessionType:
    id: str
    user_id: str
    title: Optional[str]
    is_deleted: bool
    created_at: str
    updated_at: str

@strawberry.type
class DeleteSessionPayload:
    success: bool
    message: str
    deleted_session_id: Optional[str]

@strawberry.type
class ClearHistoryPayload:
    success: bool
    message: str
    sessions_cleared_count: int


# ---------------------------------------------------------
# 2. THE MUTATIONS CLASS
# ---------------------------------------------------------
@strawberry.type
class AIBuddyMutations:
    
    @strawberry.mutation
    async def rename_chat_session(
        self, 
        info: strawberry.Info, 
        session_id: str, 
        new_title: str
    ) -> ChatSessionType:
        """
        Allows the child to manually rename a specific chat thread.
        """
        # Step 1: Extract secure context
        db: AsyncSession = info.context["db"]
        user_id = info.context["user_context"].get("user_id")
        
        if not user_id:
            raise Exception("Unauthorized: Identity verification failed.")

        # Step 2: Fetch the session strictly scoped to the authenticated user
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        session_record = result.scalars().first()

        if not session_record:
            raise Exception("Session not found or you do not have permission to edit it.")

        # Step 3: Update and Commit
        session_record.title = new_title[:100]  # Cap length for safety
        await db.commit()
        await db.refresh(session_record)

        return ChatSessionType(
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
    ) -> DeleteSessionPayload:
        """
        Soft-deletes a specific session so it disappears from the child's UI,
        but remains in the database for safety audits.
        """
        db: AsyncSession = info.context["db"]
        user_id = info.context["user_context"].get("user_id")
        
        if not user_id:
            return DeleteSessionPayload(success=False, message="Unauthorized.", deleted_session_id=None)

        # Atomic Soft Delete: More efficient than selecting then updating
        query = (
            update(ChatSession)
            .where(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .values(is_deleted=True)
            .execution_options(synchronize_session=False)
        )
        
        result = await db.execute(query)
        await db.commit()

        if result.rowcount == 0:
            return DeleteSessionPayload(
                success=False, 
                message="Session not found or already deleted.", 
                deleted_session_id=None
            )

        return DeleteSessionPayload(
            success=True, 
            message="Chat deleted successfully.", 
            deleted_session_id=session_id
        )

    @strawberry.mutation
    async def clear_all_chat_history(self, info: strawberry.Info) -> ClearHistoryPayload:
        """
        Purges the entire sidebar history for the child in one lightning-fast bulk operation.
        """
        db: AsyncSession = info.context["db"]
        user_id = info.context["user_context"].get("user_id")
        
        if not user_id:
            return ClearHistoryPayload(success=False, message="Unauthorized.", sessions_cleared_count=0)

        # Bulk Soft Delete
        query = (
            update(ChatSession)
            .where(ChatSession.user_id == user_id, ChatSession.is_deleted == False)
            .values(is_deleted=True)
            .execution_options(synchronize_session=False)
        )
        
        result = await db.execute(query)
        await db.commit()

        return ClearHistoryPayload(
            success=True, 
            message="All chat history cleared.", 
            sessions_cleared_count=result.rowcount
        )