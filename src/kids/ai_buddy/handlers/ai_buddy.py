"""
kids/ai_buddy/handlers/ai_buddy.py

The Entry Point for the Kids AI Buddy.
Optimized for Hybrid GraphQL/REST Architecture and Real-Time SSE Streaming.
"""

from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json
import logging

# Import architectural layers
from db import get_db
from kids.ai_buddy.guards import require_safe_kids_context, analyze_payload_safety
from kids.ai_buddy.schemas.ai_buddy import ChatRequest
from kids.ai_buddy.services.ai_buddy import AIBuddyService

# Professional Logger for the AI Buddy
logger = logging.getLogger("HEAL_AI_BUDDY_HANDLER")

router = APIRouter(prefix="/kids/ai-buddy", tags=["Kids AI Buddy"])

@router.post("/chat/stream")
async def handle_buddy_chat_stream(
    payload: ChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    # FIX 1: Correctly invoking the factory dependency from the updated guards.py
    user_context: dict = Depends(require_safe_kids_context()) 
):
    """
    The High-Performance Streaming Handler.
    Standardized to handle JSON payloads for SSE compatibility.
    """
    
    try:
        # 1. Extract the verified user ID from the Guard
        # THE FIX: JWT standards use "sub" for subject/identity. We check multiple keys 
        # to ensure perfect synchronization between the login generator and this handler.
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
        
        if not user_id:
            # If you still hit this, it means the JWT is completely empty of ID data.
            logger.error(f"Identity Failure. Payload received from Guard: {user_context}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="User identity could not be verified."
            )
            
        # FIX 2: Explicitly call the heuristic safety check here since we removed the wrapper decorator
        analyze_payload_safety(payload.current_message.content)
        
        # 2. Extract Session Context
        # payload.session_id can now be None (handled by our updated Schema)
        session_id = payload.session_id

        # 3. Hand over to the Service Layer
        # The service returns an AsyncGenerator which StreamingResponse pipes to the client.
        return StreamingResponse(
            AIBuddyService.process_chat_stream(
                user_id=str(user_id),
                session_id=session_id,
                raw_message=payload.current_message.content,
                provider=payload.provider,
                db=db,
                background_tasks=background_tasks
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no" # Prevents Nginx from buffering the stream
            }
        )
        
    except HTTPException:
        # Let FastAPIs normal HTTP exceptions (like our 400 Bad Request safety check) pass through
        raise
        
    except Exception as e:
        # FIX 3: Ensure logger doesn't crash if user_context is invalid during an unexpected failure
        uid = user_context.get('sub') or user_context.get('user_id') or "Unknown"
        logger.error(f"Stream initiation failed for User {uid}: {str(e)}", exc_info=True)
        
        # Secure Fallback: Send an SSE-formatted error so the frontend doesn't hang
        async def error_generator():
            error_data = json.dumps({"error": "Buddy is taking a quick nap. Try again in a second!"})
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"
            
        return StreamingResponse(error_generator(), media_type="text/event-stream")