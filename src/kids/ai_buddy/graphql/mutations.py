"""
kids/ai_buddy/graphql/mutations.py

Handles the Administrative actions for the Kids AI Buddy (Renaming, Deleting, Purging).
Implements strict Context-Aware Security to prevent ID Spoofing and atomic soft-deletes.
Now fully integrated with the Security Shield and XSS sanitization.
"""

import strawberry
import nh3
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

# [UPDATE]: Security Shield Integration
from core.exceptions import AuthenticationError, SecurityViolationError, ValidationError

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
        db: AsyncSession = info.context["db"]
        user_context = info.context.get("user_context", {})
        
        # [UPDATE]: Standardized ID extraction mirroring the handler
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
        
        if not user_id:
            # [UPDATE]: Replaced raw Exception with AuthenticationError
            raise AuthenticationError(internal_message="Rename Attempt Failed: Missing user identity in context.")

        # [UPDATE]: XSS Sanitization & Validation for the new title
        clean_title = nh3.clean(new_title, tags=set()).strip()
        if not clean_title:
            raise ValidationError(
                public_message="The new title can't be empty!",
                internal_message="Validation Fail: Empty or pure-HTML title provided for rename."
            )

        # Step 2: Fetch the session strictly scoped to the authenticated user
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        session_record = result.scalars().first()

        if not session_record:
            # [UPDATE]: Replaced raw Exception with SecurityViolationError to track potential IDOR attempts
            raise SecurityViolationError(
                internal_message=f"IDOR Prevented: User {user_id} attempted to rename unowned/nonexistent session {session_id}."
            )

        # Step 3: Update and Commit
        session_record.title = clean_title[:100]  # Cap length for safety
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
        user_context = info.context.get("user_context", {})
        
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
        
        if not user_id:
            # [UPDATE]: Replaced silent failure payload with loud internal AuthenticationError
            raise AuthenticationError(internal_message="Delete Attempt Failed: Missing user identity in context.")

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
        user_context = info.context.get("user_context", {})
        
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
        
        if not user_id:
            # [UPDATE]: Replaced silent failure payload with loud internal AuthenticationError
            raise AuthenticationError(internal_message="Clear History Attempt Failed: Missing user identity in context.")

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