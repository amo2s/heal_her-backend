import jwt
import logging
from typing import Any
from strawberry.types import Info
from strawberry.permission import BasePermission
from graphql import GraphQLError

# Adjust import to point to your central settings
from core.config import settings

logger = logging.getLogger("HEAL_SECURITY")

# =====================================================================
# THE EXTREMIST GUARD (Kids Section)
# =====================================================================
class IsKidAuthorized(BasePermission):
    """
    Triple-Lock Guard for the Kids Section.
    1. Validates Proxy Handshake (Blocks direct API hits).
    2. Validates Token Cryptography & Type (Blocks refresh tokens).
    3. Validates Role-Based Access Control (Strictly 'kid').
    """
    
    # This message is returned if has_permission returns False
    message = "Forbidden: Invalid credentials or insufficient permissions."

    async def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        # Extract FastAPI request from Strawberry context
        request = info.context.get("request")
        if not request:
            logger.error("[GUARD BLOCK] Missing request context.")
            return False

        # --- LOCK 1: THE PROXY HANDSHAKE ---
        handshake_secret = request.headers.get("x-healher-handshake")
        if not handshake_secret or handshake_secret != settings.NEXT_PUBLIC_HANDSHAKE_SECRET:
            logger.warning(f"[GUARD BLOCK] Failed proxy handshake from IP: {request.client.host}")
            return False

        # --- LOCK 2: AUTHORIZATION EXTRACTION ---
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning(f"[GUARD BLOCK] Missing/malformed Bearer token from IP: {request.client.host}")
            return False

        token = auth_header.split(" ")[1]

        # --- LOCK 3: CRYPTOGRAPHIC VERIFICATION & ROLE ENFORCEMENT ---
        try:
            # 1. Decode and verify signature & expiration automatically
            payload = jwt.decode(
                token, 
                settings.JWT_SECRET_KEY, 
                algorithms=[settings.ALGORITHM]
            )

            # 2. Token Type Enforcer
            if payload.get("type") != "access":
                logger.warning(f"[GUARD BLOCK] Attempted use of non-access token. User: {payload.get('sub')}")
                return False

            # 3. The Strict Role-Wall
            user_role = payload.get("role")
            if user_role != "kid":
                logger.warning(f"[GUARD BLOCK] Privilege Escalation Attempt! Role '{user_role}' tried to access Kids Data.")
                return False

            # 4. Extract Identity
            user_id = payload.get("sub")
            if not user_id:
                logger.error("[GUARD BLOCK] Token valid but missing subject identifier (sub).")
                return False

            # --- SECURE CONTEXT INJECTION ---
            # Inject the verified identity directly into the Strawberry context.
            # This allows handlers.py and services.py to use info.context["user_id"] 
            # with absolute cryptographic certainty.
            info.context["user_id"] = user_id
            info.context["user_role"] = user_role

            return True

        except jwt.ExpiredSignatureError:
            # When the 15-minute token dies, we throw a specific error.
            # The Next.js proxy catches this to initiate the silent refresh protocol.
            logger.info("[GUARD BLOCK] Access token expired. Triggering proxy refresh protocol.")
            raise GraphQLError("TokenExpired") 
            
        except jwt.PyJWTError as e:
            logger.error(f"[GUARD BLOCK] Cryptographic validation failed: {str(e)}")
            return False
        except Exception as e:
            logger.critical(f"[GUARD BLOCK] Unhandled security exception: {str(e)}")
            return False