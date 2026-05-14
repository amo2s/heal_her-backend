"""
src/young_adult/heal_ai/queries.py

Handles all data retrieval (Reads) for the Young Adult Heal AI.
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

# Import Young Adult-specific Models and Services
from young_adult.heal_ai.models import YoungAdultChatSession, YoungAdultChatMessage
from young_adult.heal_ai.services import decrypt_message  # [UPDATE]: Explicit service path

# Explicitly importing from the mutations module
from young_adult.heal_ai.mutations import YoungAdultChatSessionType

# Professional logger for the Young Adult Dashboard
logger = logging.getLogger("HEAL_YOUNG_ADULT_AI")
logger.setLevel(logging.WARNING)

# ---------------------------------------------------------
# 1. GRAPHQL RETURN TYPES
# ---------------------------------------------------------
@strawberry.type
class YoungAdultChatMessageType:
    """
    Represents a single message in the Heal AI session.
    The server handles decryption internally to keep the frontend clean.
    """
    id: str
    session_id: str
    role: str
    content: str  
    created_at: str


# ---------------------------------------------------------
# 2. THE SECURE QUERIES CLASS
# ---------------------------------------------------------
@strawberry.type
class HealAIQueries:
    
    @strawberry.field
    async def get_active_sessions(
        self, 
        info: Info, 
        limit: int = 30, 
        offset: int = 0
    ) -> List[YoungAdultChatSessionType]:
        """
        Populates the Young Adult Sidebar. Uses pagination and strict user scoping.
        """
        db: AsyncSession = info.context["db"]
        
        # Extract user identity from standard JWT context
        user_context = info.context.get("user_context", {})
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")

        if not user_id:
            # [UPDATE]: Replaced GraphQLError with Security Shield AuthenticationError
            raise AuthenticationError(
                internal_message="Query Failed: Identity verification failed in Young Adult get_active_sessions."
            )

        # Query only active sessions belonging to the authenticated young adult
        query = (
            select(YoungAdultChatSession)
            .where(YoungAdultChatSession.user_id == user_id, YoungAdultChatSession.is_deleted == False)
            .order_by(YoungAdultChatSession.updated_at.desc())
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
            YoungAdultChatSessionType(
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
    ) -> List[YoungAdultChatMessageType]:
        """
        Retrieves and decrypts the conversation history for a specific Heal AI session.
        """
        db: AsyncSession = info.context["db"]
        
        # Extract user identity
        user_context = info.context.get("user_context", {})
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")

        if not user_id:
            # [UPDATE]: Replaced GraphQLError with Security Shield AuthenticationError
            raise AuthenticationError(
                internal_message="Query Failed: Identity verification failed in Young Adult get_chat_history."
            )

        # SECURITY GATE: Verify session ownership before fetching messages
        session_query = (
            select(YoungAdultChatSession)
            .where(YoungAdultChatSession.id == session_id, YoungAdultChatSession.user_id == user_id)
        )
        
        session_execute_result = db.execute(session_query)
        if inspect.isawaitable(session_execute_result):
            session_check = await session_execute_result
        else:
            session_check = session_execute_result

        if not session_check.scalars().first():
            # [UPDATE]: Replaced manual logger and GraphQLError with standardized SecurityViolationError for IDOR prevention
            raise SecurityViolationError(
                internal_message=f"IDOR Prevented: User {user_id} attempted to read unowned Young Adult session {session_id}."
            )

        # Fetch message logs
        msg_query = (
            select(YoungAdultChatMessage)
            .where(YoungAdultChatMessage.session_id == session_id)
            .order_by(YoungAdultChatMessage.created_at.asc())
        )
        
        msg_execute_result = db.execute(msg_query)
        if inspect.isawaitable(msg_execute_result):
            msg_result = await msg_execute_result
        else:
            msg_result = msg_execute_result
            
        messages = msg_result.scalars().all()

        # Decryption Proxy Loop
        decrypted_history = []
        for msg in messages:
            try:
                # Decrypt the encrypted payload from the young_adult_chat_messages table
                clean_text = decrypt_message(msg.encrypted_content)
                decrypted_history.append(
                    YoungAdultChatMessageType(
                        id=msg.id,
                        session_id=msg.session_id,
                        role=msg.role,
                        content=clean_text,
                        created_at=str(msg.created_at)
                    )
                )
            except Exception as e:
                logger.error(f"Decryption failed for Young Adult message {msg.id}: {str(e)}", exc_info=True)

        return decrypted_history