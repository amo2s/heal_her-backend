"""
kids/ai_buddy/graphql/queries.py

Handles all data retrieval (Reads) for the Kids AI Buddy.
Features: Paginated Sidebar fetching, On-the-Fly Memory Decryption, and Adaptive DB Execution.
Now fully shielded against IDOR (Insecure Direct Object Reference) and data leaks.
"""

import logging
import inspect
import strawberry
from strawberry.types import Info
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# [UPDATE]: Security Shield Integration
from core.exceptions import AuthenticationError, SecurityViolationError

# Import Models and Services
from kids.ai_buddy.models import ChatSession, ChatMessage
from kids.ai_buddy.services.ai_buddy import decrypt_message

# Re-use the ChatSessionType we defined in mutations to keep the code DRY
from kids.ai_buddy.graphql.mutations import ChatSessionType

# Set up professional security logging
logger = logging.getLogger("HEAL_AI_BUDDY")
logger.setLevel(logging.WARNING)

# ---------------------------------------------------------
# 1. GRAPHQL RETURN TYPES
# ---------------------------------------------------------
@strawberry.type
class ChatMessageType:
    """
    Represents a single message in the chat.
    Notice the field is `content`, NOT `encrypted_content`. 
    The resolver handles the decryption proxy behind the scenes.
    """
    id: str
    session_id: str
    role: str
    content: str  
    created_at: str


# ---------------------------------------------------------
# 2. THE SECURE QUERIES CLASS (THE "EYES")
# ---------------------------------------------------------
@strawberry.type
class AIBuddyQueries:
    
    @strawberry.field
    async def get_active_sessions(
        self, 
        info: Info, 
        limit: int = 20, 
        offset: int = 0
    ) -> List[ChatSessionType]:
        """
        Populates the Sidebar. Uses Pagination (limit/offset) to prevent 
        database slowdowns if a child has hundreds of conversations.
        """
        db = info.context["db"]
        user_context = info.context.get("user_context", {})
        
        # [UPDATE]: Standardized Identity Extraction to match mutations/handlers
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")

        if not user_id:
            # [UPDATE]: Replaced GraphQLError with AuthenticationError
            raise AuthenticationError(
                internal_message="Query Failed: Identity verification failed in get_active_sessions."
            )

        # STRICT SCOPING: Only fetch non-deleted sessions belonging to THIS user
        query = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id, ChatSession.is_deleted == False)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        
        # --- ADAPTIVE EXECUTION ENGINE ---
        execute_result = db.execute(query)
        if inspect.isawaitable(execute_result):
            result = await execute_result
        else:
            result = execute_result
            
        sessions = result.scalars().all()

        return [
            ChatSessionType(
                id=session.id,
                user_id=session.user_id,
                title=session.title,
                is_deleted=session.is_deleted,
                created_at=str(session.created_at),
                updated_at=str(session.updated_at)
            ) for session in sessions
        ]

    @strawberry.field
    async def get_chat_history(
        self, 
        info: Info, 
        session_id: str
    ) -> List[ChatMessageType]:
        """
        The Decryption Proxy. Fetches raw encrypted data from Supabase,
        decrypts it in server memory, and sends plain text to the frontend.
        """
        db = info.context["db"]
        user_context = info.context.get("user_context", {})
        
        # [UPDATE]: Standardized Identity Extraction
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")

        if not user_id:
            raise AuthenticationError(
                internal_message="Query Failed: Identity verification failed in get_chat_history."
            )

        # SECURITY GATE: Verify the user actually owns this session_id.
        session_query = (
            select(ChatSession)
            .where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        
        # --- ADAPTIVE EXECUTION ENGINE ---
        session_execute_result = db.execute(session_query)
        if inspect.isawaitable(session_execute_result):
            session_check = await session_execute_result
        else:
            session_check = session_execute_result

        if not session_check.scalars().first():
            # [UPDATE]: Replaced leaky GraphQLError with SecurityViolationError.
            # Triggers a silent 403 Forbidden to the client while logging the exact breach attempt.
            raise SecurityViolationError(
                internal_message=f"IDOR Prevented: User {user_id} attempted to read unowned session {session_id}."
            )

        # Fetch the messages
        msg_query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        
        # --- ADAPTIVE EXECUTION ENGINE ---
        msg_execute_result = db.execute(msg_query)
        if inspect.isawaitable(msg_execute_result):
            msg_result = await msg_execute_result
        else:
            msg_result = msg_execute_result
            
        messages = msg_result.scalars().all()

        # The Decryption Loop
        decrypted_history = []
        for msg in messages:
            try:
                # Decrypt the cipher text back into readable text
                clean_text = decrypt_message(msg.encrypted_content)
                decrypted_history.append(
                    ChatMessageType(
                        id=msg.id,
                        session_id=msg.session_id,
                        role=msg.role,
                        content=clean_text,
                        created_at=str(msg.created_at)
                    )
                )
            except Exception as e:
                # [EXISTING LOGIC]: If a single message fails to decrypt, log it and skip. 
                # This ensures the entire chat doesn't crash just because one row got corrupted.
                logger.error(f"Decryption failed for message {msg.id}: {str(e)}", exc_info=True)

        return decrypted_history