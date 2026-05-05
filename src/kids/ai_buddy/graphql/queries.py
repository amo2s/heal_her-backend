"""
kids/ai_buddy/graphql/queries.py

Handles all data retrieval (Reads) for the Kids AI Buddy.
Features: Paginated Sidebar fetching, On-the-Fly Memory Decryption, and Adaptive DB Execution.
"""

import logging
import inspect
import strawberry
from strawberry.types import Info
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from graphql import GraphQLError

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
        
        # ELITE FIX: The JWT specification stores the user ID in the "sub" (Subject) claim.
        user_id = info.context["user_context"].get("sub")

        if not user_id:
            raise GraphQLError("Unauthorized: Identity verification failed.")

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
        
        # ELITE FIX: Extract ID using the standard "sub" claim
        user_id = info.context["user_context"].get("sub")

        if not user_id:
            raise GraphQLError("Unauthorized: Identity verification failed.")

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
            logger.warning(f"Unauthorized session access attempt by User: {user_id} for Session: {session_id}")
            raise GraphQLError("Access Denied: Session not found or does not belong to you.")

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
                # Upgraded to professional logging instead of basic print
                logger.error(f"Decryption failed for message {msg.id}: {str(e)}", exc_info=True)
                # We skip corrupted messages to prevent the whole query from crashing

        return decrypted_history