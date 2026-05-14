"""
kids/ai_buddy/handlers/ai_buddy.py

The Fortified Entry Point for the Kids AI Buddy.
Optimized for Hybrid GraphQL/REST Architecture and Real-Time SSE Streaming.
"""

import json
import logging
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

# [UPDATE]: Architectural Layer Imports
from db import get_db
from core.exceptions import AuthenticationError, InfrastructureError
from kids.ai_buddy.guards import require_safe_kids_context, analyze_payload_safety
from kids.ai_buddy.schemas.ai_buddy import ChatRequest
from kids.ai_buddy.services.ai_buddy import AIBuddyService

# Professional Logger
logger = logging.getLogger("HEAL_AI_BUDDY_HANDLER")

router = APIRouter(prefix="/kids/ai-buddy", tags=["Kids AI Buddy"])

@router.post("/chat/stream")
async def handle_buddy_chat_stream(
    payload: ChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    # Guard strictly enforces the 'kid' role and JWT validity
    user_context: dict = Depends(require_safe_kids_context()) 
):
    """
    The High-Performance Streaming Handler.
    Standardized for Zero-Leak error handling and SSE compatibility.
    """
    
    # 1. Identity Verification
    # [UPDATE]: standardizing ID extraction with an AuthenticationError fallback
    user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
    
    if not user_id:
        raise AuthenticationError(
            internal_message=f"Identity Failure: Guard passed empty context. Payload: {user_context}"
        )

    # 2. Content Safety Check
    # [UPDATE]: Now raises a ValidationError internally if prohibited patterns are found
    analyze_payload_safety(payload.current_message.content)

    try:
        # 3. Hand over to the Service Layer
        # The service returns an AsyncGenerator which StreamingResponse pipes to the client.
        return StreamingResponse(
            AIBuddyService.process_chat_stream(
                user_id=str(user_id),
                session_id=payload.session_id,
                raw_message=payload.current_message.content,
                provider=payload.provider,
                db=db,
                background_tasks=background_tasks
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no" # Essential for Nginx/Next.js streaming stability
            }
        )
        
    except Exception as e:
        # [UPDATE]: Fail-Safe SSE Error Generator
        # If the stream fails to initialize, we must return a valid SSE response 
        # so the frontend doesn't "hang" waiting for data.
        logger.error(f"[STREAM START FAIL] User {user_id}: {str(e)}", exc_info=True)
        
        async def error_generator():
            # [UPDATE]: User-friendly alias via JSON payload
            error_data = json.dumps({"error": "Buddy is taking a quick nap. Try again in a second!"})
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"
            
        return StreamingResponse(error_generator(), media_type="text/event-stream")