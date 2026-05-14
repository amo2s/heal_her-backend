"""
src/teens/heal_ai/graphql/mutations.py

Administrative actions for Teens Heal AI.
Provides renaming, soft-deleting, and bulk purging of session history.
Now fully integrated with the Security Shield and XSS sanitization to guarantee Zero-Leak operations.
"""

import strawberry
import nh3
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

# [UPDATE]: Security Shield Integration
from core.exceptions import AuthenticationError, SecurityViolationError, ValidationError

# Import the teens-specific models
from teens.heal_ai.models import TeensChatSession

# ---------------------------------------------------------
# 1. GRAPHQL RETURN TYPES (PAYLOAD PATTERN)
# ---------------------------------------------------------
@strawberry.type
class TeensChatSessionType:
    id: str
    user_id: str
    title: Optional[str]
    is_deleted: bool
    created_at: str
    updated_at: str

@strawberry.type
class TeensDeleteSessionPayload:
    success: bool
    message: str
    deleted_session_id: Optional[str]

@strawberry.type
class TeensClearHistoryPayload:
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
    ) -> TeensChatSessionType:
        """
        Allows the user to manually rename a specific Heal AI session.
        """
        db: AsyncSession = info.context["db"]
        
        # Identity Extraction: Aligning with the bulletproof sub/user_id check
        user_context = info.context.get("user_context", {})
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
        
        if not user_id:
            # [UPDATE]: Replaced raw Exception with standardized AuthenticationError
            raise AuthenticationError(internal_message="Rename Attempt Failed: Missing user identity in context.")

        # [UPDATE]: XSS Sanitization & Validation for the new title (Prevents GraphQL Injection)
        clean_title = nh3.clean(new_title, tags=set()).strip()
        if not clean_title:
            raise ValidationError(
                public_message="The session title cannot be empty.",
                internal_message="Validation Fail: Empty or pure-HTML title provided for Teens session rename."
            )

        # Scoped fetch: Ensure the session belongs to the authenticated teen
        result = await db.execute(
            select(TeensChatSession)
            .where(TeensChatSession.id == session_id, TeensChatSession.user_id == user_id)
        )
        session_record = result.scalars().first()

        if not session_record:
            # [UPDATE]: Replaced raw Exception with SecurityViolationError to track potential IDOR attempts
            raise SecurityViolationError(
                internal_message=f"IDOR Prevented: User {user_id} attempted to rename unowned/nonexistent Teens session {session_id}."
            )

        # Update and Commit
        session_record.title = clean_title[:100]  # Respect database constraints
        await db.commit()
        await db.refresh(session_record)

        return TeensChatSessionType(
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
    ) -> TeensDeleteSessionPayload:
        """
        Soft-deletes a session. It remains in DB for safety/audit but is removed from UI.
        """
        db: AsyncSession = info.context["db"]
        user_context = info.context.get("user_context", {})
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
        
        if not user_id:
            # [UPDATE]: Replaced silent failure payload with loud internal AuthenticationError
            raise AuthenticationError(internal_message="Delete Attempt Failed: Missing user identity in context.")

        # Atomic Soft Delete
        query = (
            update(TeensChatSession)
            .where(TeensChatSession.id == session_id, TeensChatSession.user_id == user_id)
            .values(is_deleted=True)
            .execution_options(synchronize_session=False)
        )
        
        result = await db.execute(query)
        await db.commit()

        if result.rowcount == 0:
            return TeensDeleteSessionPayload(
                success=False, 
                message="Session not found or already archived.", 
                deleted_session_id=None
            )

        return TeensDeleteSessionPayload(
            success=True, 
            message="Session archived successfully.", 
            deleted_session_id=session_id
        )

    @strawberry.mutation
    async def clear_all_chat_history(self, info: strawberry.Info) -> TeensClearHistoryPayload:
        """
        Performs a bulk soft-delete of all active sessions for the current teen.
        """
        db: AsyncSession = info.context["db"]
        user_context = info.context.get("user_context", {})
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
        
        if not user_id:
            # [UPDATE]: Replaced silent failure payload with loud internal AuthenticationError
            raise AuthenticationError(internal_message="Clear History Attempt Failed: Missing user identity in context.")

        # Bulk Atomic Soft Delete
        query = (
            update(TeensChatSession)
            .where(TeensChatSession.user_id == user_id, TeensChatSession.is_deleted == False)
            .values(is_deleted=True)
            .execution_options(synchronize_session=False)
        )
        
        result = await db.execute(query)
        await db.commit()

        return TeensClearHistoryPayload(
            success=True, 
            message="Heal AI history cleared successfully.", 
            sessions_cleared_count=result.rowcount
        )