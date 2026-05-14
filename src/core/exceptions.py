"""
src/core/exceptions.py

The Central Security Shield for Error Handling.
This file maps raw, dangerous internal errors to clean, safe public aliases.
"""

import logging
from fastapi import Request
from fastapi.responses import JSONResponse

# Professional Security Logger
logger = logging.getLogger("HEAL_AI_SECURITY")
logger.setLevel(logging.ERROR)

# ---------------------------------------------------------
# 1. THE BASE EXCEPTION CLASS
# ---------------------------------------------------------
class HealAIException(Exception):
    """
    The Base exception that strictly separates internal logs from public UI messages.
    """
    def __init__(self, public_message: str, internal_message: str = None, status_code: int = 400):
        self.public_message = public_message
        self.internal_message = internal_message or public_message
        self.status_code = status_code
        
        # 1. Immediately log the REAL, dirty error to the backend console
        logger.error(f"[SYSTEM ALERT] {self.internal_message}")
        
        # 2. Set the standard Python Exception string to the PUBLIC message.
        # If Strawberry (GraphQL) catches this raw, it will only ever transmit this safe string to the UI.
        super().__init__(self.public_message)


# ---------------------------------------------------------
# 2. THE ERROR BUCKETS (Subclasses)
# ---------------------------------------------------------
class AuthenticationError(HealAIException):
    """Triggered on wrong passwords, missing users, or expired JWTs."""
    def __init__(self, internal_message: str = "Authentication failed"):
        super().__init__(
            public_message="Invalid credentials or session expired.",
            internal_message=internal_message,
            status_code=401
        )

class SecurityViolationError(HealAIException):
    """Triggered on role mismatches, token tampering, or cross-domain spoofing."""
    def __init__(self, internal_message: str = "Security boundary breach"):
        super().__init__(
            public_message="Access denied. Invalid security context.",
            internal_message=internal_message,
            status_code=403
        )

class InfrastructureError(HealAIException):
    """Triggered when Redis, Postgres, or the AI Provider goes offline."""
    def __init__(self, internal_message: str = "Infrastructure component failure"):
        super().__init__(
            public_message="System is currently busy. Please try again later.",
            internal_message=internal_message,
            status_code=503
        )

class ValidationError(HealAIException):
    """Triggered when the user sends malformed data (e.g., bad email format)."""
    def __init__(self, public_message: str, internal_message: str = "Data validation failed"):
        super().__init__(
            public_message=public_message,
            internal_message=internal_message,
            status_code=400
        )

class NotFoundError(HealAIException):
    """Triggered when a requested resource (like an old chat session) doesn't exist."""
    def __init__(self, public_message: str = "Resource not found", internal_message: str = "Entity not found in database"):
        super().__init__(
            public_message=public_message,
            internal_message=internal_message,
            status_code=404
        )


# ---------------------------------------------------------
# 3. FASTAPI GLOBAL INTERCEPTORS (For REST Endpoints like /stream)
# ---------------------------------------------------------
async def heal_ai_exception_handler(request: Request, exc: HealAIException):
    """
    Catches our custom exceptions leaving REST endpoints and formats them safely.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.public_message} # Strict leak prevention
    )

async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    The Ultimate Fail-Safe. If a completely unexpected Python error occurs (like a SyntaxError or ZeroDivisionError),
    this catches it before FastAPI can leak the stack trace to the browser.
    """
    logger.critical(f"[CRITICAL UNHANDLED ERROR] {request.url} - {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "System is currently busy. Please try again later."}
    )