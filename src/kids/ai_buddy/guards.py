"""
kids/ai_buddy/guards.py

Strict security, authentication, and content safety layer for the Kids AI Buddy.
Now 100% integrated with the central Security Shield.
"""

import re
import logging
from typing import Callable, Any, Dict
from fastapi import Request

# --- THE CORRECTED IMPORTS ---
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError, JWTClaimsError

from core.config import settings

# [UPDATE]: Imported the centralized Security Shield buckets. 
# Zero usage of raw FastAPI HTTPExceptions allowed from here on out.
from core.exceptions import SecurityViolationError, AuthenticationError, ValidationError

# Setup logging to catch token issues in development
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
            # [UPDATE]: Replaced 400 HTTPException with ValidationError.
            # The internet gets a clean safety message. You get the exact regex trigger in your logs.
            raise ValidationError(
                public_message="Message violates HEAL Her safety guardrails.",
                internal_message=f"Heuristic Trigger: Prohibited pattern '{pattern.pattern}' detected in payload."
            )


# ---------------------------------------------------------
# 2. CORE AUTHENTICATION ENGINE
# ---------------------------------------------------------
def decode_and_verify_kids_token(token: str) -> Dict[str, Any]:
    """
    Decodes the actual JWT using your vault settings.
    Strictly enforces the 'kid' role assigned during signup and validates audience.
    """
    # [UPDATE]: Defensive Null-Check before string manipulation to prevent 500 crashes
    if not token:
        raise AuthenticationError(internal_message="Empty token provided to decode engine.")

    # Clean up token to prevent parsing errors from proxy/SSE transfers
    sanitized_token = token.strip().replace('"', '').replace("'", "")

    try:
        payload = jwt.decode(
            sanitized_token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.ALGORITHM],
            audience="kids"  # Strictly enforce the 'kids' audience
        )
        
        # Explicitly read the role injected by login.py
        token_role = payload.get("role")
        
        # LOGIC CHECK: Match the dashboard role ('kid')
        if token_role != "kid":
            # [UPDATE]: Prevented Role Leak. Hacker gets "Access Denied", 
            # backend logs exactly which sector tried to breach the Kids zone.
            raise SecurityViolationError(
                internal_message=f"Sector Breach Attempt: User with role '{token_role}' tried to access /kids."
            )
            
        return payload
        
    except ExpiredSignatureError:
        # [UPDATE]: Seamless mapping to 401 bucket
        raise AuthenticationError(internal_message="JWT Verification Failed: Session expired.")
        
    except JWTClaimsError as e:
        # [UPDATE]: Obfuscated Cross-Domain spoofing. 
        # If someone uses a 'teens' token here, we log it silently and deny access.
        raise SecurityViolationError(
            internal_message=f"Audience Mismatch (Cross-Domain Spoofing Attempt): {str(e)}"
        )
        
    except JWTError as e:
        # Catch-all for malformed tokens, bad signatures, etc.
        logger.error(f"JWT Verification Failed: {str(e)}")
        raise AuthenticationError(internal_message=f"Invalid security token: {str(e)}")


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
        # [UPDATE]: Replaced raw HTTPException
        raise AuthenticationError(
            internal_message="Missing or invalid Authorization header in GraphQL request."
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
            # [UPDATE]: Replaced raw HTTPException
            raise AuthenticationError(
                internal_message="Missing or invalid Authorization header in REST stream request."
            )

        token = auth_header.split(" ")[1]
        return decode_and_verify_kids_token(token)
        
    return dependency