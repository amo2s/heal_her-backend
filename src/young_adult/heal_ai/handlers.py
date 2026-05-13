"""
src/young_adult/heal_ai/handlers/heal_ai.py

The Entry Point for the Young-Adult Heal AI.
Optimized for Hybrid GraphQL/REST Architecture and Real-Time SSE Streaming.
"""

import json
import logging
from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

# Import architectural layers (File paths use underscores)
from db import get_db
from young_adult.heal_ai.guards import require_safe_young_adult_context, analyze_payload_safety
from young_adult.heal_ai.schemas import ChatRequest
from young_adult.heal_ai.services import HealAIService

# Professional Logger for the Young-Adult AI (Internal logic uses hyphens)
logger = logging.getLogger("HEAL-YOUNG-ADULT-AI-HANDLER")

# Router configuration using hyphens as requested
router = APIRouter(prefix="/young_adult/heal-ai", tags=["Young-Adult Heal AI"])

@router.post("/chat/stream")
async def handle_heal_chat_stream(
    payload: ChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    # Dependency aligned with the young-adult context
    user_context: dict = Depends(require_safe_young_adult_context()) 
):
    """
    The High-Performance Streaming Handler for Young-Adult Heal AI.
    Standardized to handle JSON payloads for SSE compatibility with mature safety checks.
    """
    
    try:
        # 1. Extract the verified user ID from the Guard
        user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
        
        if not user_id:
            logger.error(f"Identity Verification Failed. Context received: {user_context}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="User identity could not be verified."
            )
            
        # 2. Heuristic Safety Check
        # Analyzes the young-adult's input for severe prohibited patterns before processing.
        analyze_payload_safety(payload.current_message.content)
        
        # 3. Session Context
        session_id = payload.session_id

        # 4. Hand over to the Service Layer
        # The service returns an AsyncGenerator which StreamingResponse pipes to the client.
        return StreamingResponse(
            HealAIService.process_chat_stream(
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
                "X-Accel-Buffering": "no" # Essential for real-time delivery through Nginx
            }
        )
        
    except HTTPException:
        # Pass through standard HTTP exceptions
        raise
        
    except Exception as e:
        uid = user_context.get('sub') or user_context.get('user_id') or "Unknown"
        logger.error(f"Stream initiation failed for Young-Adult User {uid}: {str(e)}", exc_info=True)
        
        # Secure Fallback: Return a professional SSE-formatted error
        async def error_generator():
            error_data = json.dumps({
                "error": "Heal AI is temporarily unavailable. Please try again in a few moments."
            })
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"
            
        return StreamingResponse(error_generator(), media_type="text/event-stream")