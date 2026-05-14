"""
src/young_adult/heal_ai/handlers/heal_ai.py

The Fortified Entry Point for the Young-Adult Heal AI.
Optimized for Hybrid GraphQL/REST Architecture and Real-Time SSE Streaming.
Integrated with the HEAL Security Shield for Zero-Leak operation.
"""

import json
import logging
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

# [UPDATE]: Architectural Layer Imports aligned with Security Shield
from db import get_db
from core.exceptions import AuthenticationError
from young_adult.heal_ai.guards import require_safe_young_adult_context, analyze_payload_safety
from young_adult.heal_ai.schemas import ChatRequest
from young_adult.heal_ai.services  import HealAIService  # [UPDATE]: Explicit service path

# Professional Logger for the Young-Adult AI
logger = logging.getLogger("HEAL_YOUNG_ADULT_AI_HANDLER")

# Router configuration strictly preserving the requested pathing
router = APIRouter(prefix="/young_adult/heal-ai", tags=["Young-Adult Heal AI"])

@router.post("/chat/stream")
async def handle_heal_chat_stream(
    payload: ChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    # Guard strictly enforces the role and JWT validity.
    # If the guard fails, it raises a Shielded AuthenticationError automatically.
    user_context: dict = Depends(require_safe_young_adult_context()) 
):
    """
    The High-Performance Streaming Handler for Young-Adult Heal AI.
    Standardized for Zero-Leak error handling and SSE compatibility with mature safety checks.
    """
    
    # 1. Identity Verification
    user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
    
    if not user_id:
        # Shielded AuthenticationError replaces raw HTTP exceptions
        raise AuthenticationError(
            internal_message=f"Identity Failure: Guard passed empty context for young-adult. Payload: {user_context}"
        )

    # 2. Heuristic Safety Check
    # Analyzes the input for severe prohibited patterns before processing.
    # Raises a ValidationError internally if prohibited patterns are found.
    analyze_payload_safety(payload.current_message.content)
    
    try:
        # 3. Hand over to the Service Layer
        return StreamingResponse(
            HealAIService.process_chat_stream(
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
                "X-Accel-Buffering": "no" # Essential for real-time delivery through Nginx/Next.js
            }
        )
        
    except Exception as e:
        # Secure Fallback: Return a professional SSE-formatted error
        logger.error(f"[STREAM START FAIL] Young-Adult User {user_id}: {str(e)}", exc_info=True)
        
        async def error_generator():
            error_data = json.dumps({
                "error": "Heal AI is temporarily unavailable. Please try again in a few moments."
            })
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"
            
        return StreamingResponse(error_generator(), media_type="text/event-stream")