import strawberry
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional

# [UPDATE]: Import the central Security Shield exceptions.
# Aliased ValidationError to ShieldValidationError to prevent namespace crashes with Pydantic.
from core.exceptions import (
    ValidationError as ShieldValidationError,
    SecurityViolationError
)

# =====================================================================
# 1. THE PYDANTIC FIREWALL (STRICT VALIDATION)
# =====================================================================
class LoginValidationSchema(BaseModel):
    """
    The absolute authority on what data is allowed into the system.
    If it doesn't pass this, it dies here.
    """
    email: EmailStr = Field(
        ..., 
        description="Strictly validates RFC 5322 email format."
    )
    
    # THE 72-CHARACTER HARD CAP: Argon2id and Bcrypt can truncate or 
    # become vulnerable to DoS if fed massive strings. We cap it ruthlessly.
    password: str = Field(
        ..., 
        min_length=8, 
        max_length=72, 
        description="Password must be between 8 and 72 characters."
    )
    
    bot_trap: Optional[str] = None

    # --- CUSTOM VALIDATORS ---

    @field_validator("email")
    @classmethod
    def sanitize_email(cls, v: str) -> str:
        """
        [UPDATE]: Centralized Cleaning. 
        Forces email to lowercase and strips whitespace here at the core, 
        guaranteeing it's clean regardless of how it entered the system.
        """
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def enforce_password_security(cls, v: str) -> str:
        """
        [UPDATE]: UX vs. Security Message Splitting.
        If a hacker tries to DoS the server with a 10,000-character password, 
        we block it and give a generic response so they don't know our limit.
        """
        if len(v) > 72:
            raise ShieldValidationError(
                public_message="Invalid login credentials.",
                internal_message=f"Login password length exceeded 72-char DoS cap. Length attempted: {len(v)}"
            )
        return v

    @field_validator("bot_trap")
    @classmethod
    def check_bot_trap(cls, v: Optional[str]) -> Optional[str]:
        """If a bot fills this invisible field, the payload is destroyed."""
        if v:
            # [UPDATE]: Escalated from a standard ValueError to a SecurityViolationError.
            # This flags the global interceptor to return 403 Forbidden and log a high-priority alert.
            raise SecurityViolationError(
                internal_message=f"Login Security Honeypot triggered. Hidden payload: {v}"
            )
        return v


# =====================================================================
# 2. THE STRAWBERRY INPUT (GRAPHQL BRIDGE)
# =====================================================================
@strawberry.input
class LoginInput:
    """
    What the frontend sends via the GraphQL Mutation.
    """
    email: str
    password: str
    bot_trap: Optional[str] = strawberry.field(default=None)

    def validate_and_clean(self) -> LoginValidationSchema:
        """
        Forces the GraphQL input through the Pydantic Firewall.
        """
        # [UPDATE]: Made the bridge "Skinny".
        # We removed manual string manipulation from this layer. 
        # Pydantic handles all the lowering and stripping automatically now.
        return LoginValidationSchema(
            email=self.email,
            password=self.password,
            bot_trap=self.bot_trap
        )


# =====================================================================
# 3. THE STRAWBERRY OUTPUT TYPES (SAFE PAYLOADS)
# =====================================================================
@strawberry.type
class UserType:
    """
    The sanitized user object. 
    Notice what is MISSING: No password hashes, no internal database IDs.
    """
    id: str
    email: str
    full_name: str
    is_active: bool
    dashboard: str    # Forces the frontend to route to the correct segment


@strawberry.type
class LoginResponse:
    """
    The success payload. The proxy will strip the access_token into an HttpOnly 
    cookie and only send the UserType back to the browser.
    """
    status: str
    message: str
    access_token: str
    refresh_token: str
    user: UserType