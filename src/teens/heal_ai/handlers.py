"""
src/teens/heal_ai/handlers/heal_ai.py

The Fortified Entry Point for the Teens Heal AI.
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
from teens.heal_ai.guards import require_safe_teen_context, analyze_payload_safety
from teens.heal_ai.schemas import ChatRequest
from teens.heal_ai.services import HealAIService # [UPDATE]: Explicit service path

# Professional Logger for the Teens AI
logger = logging.getLogger("HEAL_TEENS_AI_HANDLER")

router = APIRouter(prefix="/teens/heal-ai", tags=["Teens Heal AI"])

@router.post("/chat/stream")
async def handle_heal_chat_stream(
    payload: ChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    # [UPDATE]: Guard strictly enforces the 'teen' role and JWT validity.
    # If the guard fails, it raises a Shielded AuthenticationError automatically.
    user_context: dict = Depends(require_safe_teen_context()) 
):
    """
    The High-Performance Streaming Handler for Heal AI.
    Standardized for Zero-Leak error handling and SSE compatibility with mature safety checks.
    """
    
    # 1. Identity Verification
    # [UPDATE]: Standardized ID extraction mirroring the Kids sector and Auth architecture.
    user_id = user_context.get("sub") or user_context.get("user_id") or user_context.get("id")
    
    if not user_id:
        # If identity is missing from a verified token, we log a high-priority security anomaly.
        raise AuthenticationError(
            internal_message=f"Identity Failure: Guard passed empty context for teen. Payload: {user_context}"
        )

    # 2. Heuristic Safety Check
    # [UPDATE]: Now raises a ValidationError internally if prohibited patterns are found.
    # This prevents the request from hitting the service layer if unsafe content is detected.
    analyze_payload_safety(payload.current_message.content)
    
    try:
        # 3. Hand over to the Service Layer
        # The service returns an AsyncGenerator which StreamingResponse pipes to the client.
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
        # [UPDATE]: Fail-Safe SSE Error Generator
        # Ensures that if the stream initiation crashes (e.g. LLM provider down), 
        # the frontend receives a structured [DONE] signal instead of a pending hang.
        logger.error(f"[STREAM START FAIL] Teen User {user_id}: {str(e)}", exc_info=True)
        
        async def error_generator():
            # Standardized supportive message for the teen demographic
            error_data = json.dumps({
                "error": "Heal AI is temporarily unavailable. Please try again in a few moments."
            })
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"
            
        return StreamingResponse(error_generator(), media_type="text/event-stream")