import re
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator
from typing import Optional

# [UPDATE]: Import the central Security Shield exceptions.
# We alias ValidationError to ShieldValidationError to prevent catastrophic 
# namespace collisions with Pydantic's native pydantic_core.ValidationError.
from core.exceptions import (
    ValidationError as ShieldValidationError,
    SecurityViolationError
)

class SignupInputSchema(BaseModel):
    """
    EXTREMIST SECURITY SCHEMA:
    Validates incoming GraphQL signup requests with ruthless strictness.
    Now includes age-based routing requirements and Security Shield integration.
    """
    
    # --- MODEL CONFIGURATION ---
    model_config = ConfigDict(
        extra="forbid",               # 🚫 INSTANT REJECT if hidden fields are injected
        str_strip_whitespace=True,    # ✂️ Auto-trim all leading/trailing spaces
        str_to_lower=False            # Explicitly handled in validators
    )

    # --- FIELD DEFINITIONS & REGEX FIREWALLS ---
    
    full_name: str = Field(
        ..., 
        min_length=2, 
        max_length=50,
        pattern=r"^[A-Za-z\s\-\']+$", 
        description="Strictly alphabetical. Blocks injection attempts."
    )
    
    email: EmailStr = Field(
        ...,
        max_length=255, 
        description="Standard structural email validation with strict length limit."
    )

    age: int = Field(
        ...,
        ge=5,   # Minimum age 5 (Protects against toddlers/invalid data)
        le=120, # Maximum age 120 (Reasonable human limit)
        description="User age. Determines dashboard segment: Kids, Teens, or Young Adults."
    )
    
    password: str = Field(
        ...,
        min_length=8,
        max_length=128, 
        description="MUST contain: 1 uppercase, 1 lowercase, 1 number, 1 special character."
    )
    
    bot_trap: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Honeypot field. Must remain empty."
    )

    # --- CUSTOM VALIDATORS ---

    @field_validator('full_name')
    @classmethod
    def sanitize_full_name(cls, v: str) -> str:
        """
        [UPDATE]: Name Firewall Enhancement.
        Prevents "hidden" duplicates by normalizing internal spacing.
        (e.g., "Nwaka   Amos" becomes "Nwaka Amos").
        """
        return re.sub(r'\s+', ' ', v).strip()

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Strictly checks for uppercase, lowercase, number, and special character."""
        # [UPDATE]: UX vs. Security Message Splitting. 
        # The frontend gets a generic, unhelpful message. The terminal gets the exact reason.
        public_msg = "Password does not meet security requirements."
        
        if not any(c.islower() for c in v):
            raise ShieldValidationError(public_message=public_msg, internal_message="Password failed 'lowercase' check.")
        if not any(c.isupper() for c in v):
            raise ShieldValidationError(public_message=public_msg, internal_message="Password failed 'uppercase' check.")
        if not any(c.isdigit() for c in v):
            raise ShieldValidationError(public_message=public_msg, internal_message="Password failed 'digit' check.")
        
        special_chars = "@$!%*?&_"
        if not any(c in special_chars for c in v):
            raise ShieldValidationError(public_message=public_msg, internal_message="Password failed 'special character' check.")
        
        return v

    @field_validator('email')
    @classmethod
    def force_lowercase_email(cls, v: str) -> str:
        """Ensures all emails are strictly lowercase to prevent duplicate account creation."""
        return v.lower()

    @field_validator('bot_trap')
    @classmethod
    def ensure_honeypot_empty(cls, v: Optional[str]) -> Optional[str]:
        """Secondary check: if the honeypot has ANY value, fail validation."""
        if v:
            # [UPDATE]: Escalated from a standard validation error to a Security Violation.
            # This triggers the specific 403 bucket in the global exception handler.
            raise SecurityViolationError(
                internal_message=f"Honeypot filled during schema validation. Hidden payload: {v}"
            ) 
        return v