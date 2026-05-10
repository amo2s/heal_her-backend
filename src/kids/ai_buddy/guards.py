"""
kids/ai_buddy/guards.py

Strict security, authentication, and content safety layer for the Kids AI Buddy.
Provides both the REST Dependency and the GraphQL Dependency.
"""

import re
import jwt
import logging # ADDED: For token debugging to match the new architecture
from typing import Callable, Any, Dict
from fastapi import HTTPException, status, Request
from core.config import settings

# ADDED: Setup logging to catch token issues in development
logger = logging.getLogger("HEAL_SECURITY_GUARD_KIDS")

# ---------------------------------------------------------
# 1. CONTENT SAFETY ENGINE (Heuristic Checks)
# ---------------------------------------------------------
# Pre-compiled regex for maximum throughput during safety checks
PROHIBITED_PATTERNS = [
    re.compile(r"\b(kill|suicide|drugs|violence|sex|hate)\b", re.IGNORECASE),
    # Expand this list as needed for immediate keyword blocking
]

def analyze_payload_safety(payload: str) -> None:
    """Executes heuristic checks to block unsafe inputs immediately."""
    for pattern in PROHIBITED_PATTERNS:
        if pattern.search(payload):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message violates HEAL Her safety guardrails."
            )


# ---------------------------------------------------------
# 2. CORE AUTHENTICATION ENGINE
# ---------------------------------------------------------
def decode_and_verify_kids_token(token: str) -> Dict[str, Any]:
    """
    Decodes the actual JWT using your vault settings.
    Strictly enforces the 'kid' role assigned during signup and validates audience.
    """
    try:
        # SECURITY FIX 1: Clean up token to prevent parsing errors from proxy/SSE transfers
        sanitized_token = token.strip().replace('"', '').replace("'", "")

        payload = jwt.decode(
            sanitized_token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.ALGORITHM],
            # SECURITY FIX 2: Strictly enforce the 'kids' audience to align with the new login.py requirements
            audience="kids"
        )
        
        # ELITE UPGRADE: We now explicitly read the role injected by login.py
        token_role = payload.get("role")
        
        # LOGIC CHECK: Match the dashboard role ('kid')
        if token_role != "kid":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: This space is strictly for kids. Your role is '{token_role}'."
            )
            
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")
    except jwt.InvalidAudienceError:
        # SECURITY FIX 3: Catch cross-domain spoofing if a teen or admin tries to access the kids route
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-Domain Spoofing Blocked: Token does not belong to the kids sector."
        )
    except jwt.InvalidTokenError as e:
        # SECURITY FIX 4: Added logging to expose the exact reason for a 401 failure in the console
        logger.error(f"JWT Verification Failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid security token.")


# ---------------------------------------------------------
# 3. GRAPHQL DEPENDENCY
# ---------------------------------------------------------
async def verify_kids_jwt_dependency(request: Request) -> Dict[str, Any]:
    """
    Extracts the token from the Authorization header for GraphQL requests.
    This is what router.py imports to secure your queries and mutations.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing or invalid Authorization header."
        )
    
    token = auth_header.split(" ")[1]
    return decode_and_verify_kids_token(token)


# ---------------------------------------------------------
# 4. REST STREAMING DEPENDENCY FACTORY
# ---------------------------------------------------------
def require_safe_kids_context() -> Callable:
    """
    FastAPI Dependency Factory for /chat/stream. 
    Replaces the old decorator to properly inject verified user context
    without triggering the 'func' query parameter error.
    """
    async def dependency(request: Request) -> Dict[str, Any]:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Authentication required."
            )

        token = auth_header.split(" ")[1]
        return decode_and_verify_kids_token(token)
        
    return dependency