"""
src/young_adult/heal_ai/guards.py

Strict security, authentication, and content safety layer for the Young Adult Heal AI.
Provides both the REST Dependency and the GraphQL Dependency.
"""

import re
import jwt
import logging
from typing import Callable, Any, Dict
from fastapi import HTTPException, status, Request
from core.config import settings

# Setup logging to catch token issues in development
logger = logging.getLogger("HEAL_SECURITY_GUARD")

# ---------------------------------------------------------
# 1. CONTENT SAFETY ENGINE (Heuristic Checks)
# ---------------------------------------------------------
PROHIBITED_PATTERNS = [
    re.compile(r"\b(kill myself|suicide plan|buy drugs|sell drugs|child porn|rape|murder)\b", re.IGNORECASE),
]

def analyze_payload_safety(payload: str) -> None:
    """Executes heuristic checks to block severely unsafe inputs immediately."""
    for pattern in PROHIBITED_PATTERNS:
        if pattern.search(payload):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "This topic requires professional support. "
                    "Please use the Emergency SOS feature or reach out to a trusted contact in your Safe Circle immediately."
                )
            )


# ---------------------------------------------------------
# 2. CORE AUTHENTICATION ENGINE
# ---------------------------------------------------------
def decode_and_verify_young_adult_token(token: str) -> Dict[str, Any]:
    """
    Decodes the actual JWT using your vault settings.
    Strictly enforces the 'young_adult' role assigned during signup and verifies audience.
    """
    try:
        # CLEANUP: Remove potential extra quotes (common in proxy/storage transfers)
        sanitized_token = token.strip().replace('"', '').replace("'", "")

        payload = jwt.decode(
            sanitized_token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.ALGORITHM],
            # THE FIX: We now strictly enforce the "young_adult" audience to match login.py
            audience="young_adult" 
        )
        
        # Explicitly read the role injected by the auth service
        token_role = payload.get("role")
        
        # LOGIC CHECK: Match the dashboard role ('young_adult')
        if token_role != "young_adult":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Heal AI is strictly for young adults. Your role is '{token_role}'."
            )
            
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Session expired. Please log in again."
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-Domain Spoofing Blocked: Token does not belong to the young adult sector."
        )
    except jwt.InvalidTokenError as e:
        # Debugging: Log the error to see why verification failed (Secret mismatch, etc.)
        logger.error(f"JWT Verification Failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid security token."
        )


# ---------------------------------------------------------
# 3. GRAPHQL DEPENDENCY
# ---------------------------------------------------------
async def verify_young_adult_jwt_dependency(request: Request) -> Dict[str, Any]:
    """
    Extracts the token from the Authorization header for GraphQL requests.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing or invalid Authorization header."
        )
    
    token = auth_header.split(" ")[1]
    return decode_and_verify_young_adult_token(token)


# ---------------------------------------------------------
# 4. REST STREAMING DEPENDENCY FACTORY
# ---------------------------------------------------------
def require_safe_young_adult_context() -> Callable:
    """
    FastAPI Dependency Factory for /chat/stream. 
    Properly injects verified user context for the streaming REST endpoint.
    """
    async def dependency(request: Request) -> Dict[str, Any]:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Authentication required."
            )

        token = auth_header.split(" ")[1]
        return decode_and_verify_young_adult_token(token)
        
    return dependency