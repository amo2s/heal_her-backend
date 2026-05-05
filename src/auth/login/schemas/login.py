import strawberry
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional

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

    @field_validator("bot_trap")
    @classmethod
    def check_bot_trap(cls, v: Optional[str]) -> Optional[str]:
        """If a bot fills this invisible field, the payload is destroyed."""
        if v:
            raise ValueError("Security Honeypot triggered. Payload rejected.")
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
        Raises ValueError which we will catch in the resolver.
        """
        # Lowercase and strip the email to prevent case-sensitive duplicate attacks
        clean_email = self.email.lower().strip()
        
        return LoginValidationSchema(
            email=clean_email,
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