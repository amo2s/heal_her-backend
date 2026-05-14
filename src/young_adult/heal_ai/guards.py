"""
src/young_adult/heal_ai/guards.py

Strict security, authentication, and content safety layer for the Young Adult Heal AI.
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
            # [UPDATE]: Replaced 400 HTTPException with ValidationError.
            # Preserves the critical public SOS message while securely logging the exact regex match internally.
            raise ValidationError(
                public_message=(
                    "This topic requires professional support. "
                    "Please use the Emergency SOS feature or reach out to a trusted contact in your Safe Circle immediately."
                ),
                internal_message=f"Heuristic Trigger: Prohibited emergency pattern '{pattern.pattern}' detected in payload."
            )


# ---------------------------------------------------------
# 2. CORE AUTHENTICATION ENGINE
# ---------------------------------------------------------
def decode_and_verify_young_adult_token(token: str) -> Dict[str, Any]:
    """
    Decodes the actual JWT using your vault settings.
    Strictly enforces the 'young_adult' role assigned during signup and verifies audience.
    """
    # [UPDATE]: Defensive Null-Check before string manipulation to prevent 500 crashes.
    if not token:
        raise AuthenticationError(internal_message="Empty token provided to decode engine.")

    # CLEANUP: Remove potential extra quotes (common in proxy/storage transfers)
    sanitized_token = token.strip().replace('"', '').replace("'", "")

    try:
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
            # [UPDATE]: Prevented Role Leak. Hacker gets a generic 403 response, 
            # while the backend logs exactly which sector tried to breach the Young Adult zone.
            raise SecurityViolationError(
                internal_message=f"Sector Breach Attempt: User with role '{token_role}' tried to access /young_adult."
            )
            
        return payload
        
    except ExpiredSignatureError:
        # [UPDATE]: Seamless mapping to the 401 AuthenticationError bucket.
        raise AuthenticationError(internal_message="JWT Verification Failed: Session expired.")
        
    except JWTClaimsError as e:
        # [UPDATE]: Obfuscated Cross-Domain spoofing. 
        # If someone uses a 'kids' or 'teens' token here, we log it silently and deny access.
        raise SecurityViolationError(
            internal_message=f"Audience Mismatch (Cross-Domain Spoofing Attempt): {str(e)}"
        )
        
    except JWTError as e:
        # Debugging: Log the error to see why verification failed (Secret mismatch, etc.)
        logger.error(f"JWT Verification Failed: {str(e)}")
        raise AuthenticationError(internal_message=f"Invalid security token: {str(e)}")


# ---------------------------------------------------------
# 3. GRAPHQL DEPENDENCY
# ---------------------------------------------------------
async def verify_young_adult_jwt_dependency(request: Request) -> Dict[str, Any]:
    """
    Extracts the token from the Authorization header for GraphQL requests.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        # [UPDATE]: Replaced raw HTTPException.
        raise AuthenticationError(
            internal_message="Missing or invalid Authorization header in GraphQL request."
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
            # [UPDATE]: Replaced raw HTTPException.
            raise AuthenticationError(
                internal_message="Missing or invalid Authorization header in REST stream request."
            )

        token = auth_header.split(" ")[1]
        return decode_and_verify_young_adult_token(token)
        
    return dependency