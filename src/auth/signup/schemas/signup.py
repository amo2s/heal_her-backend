import re
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator
from typing import Optional

class SignupInputSchema(BaseModel):
    """
    EXTREMIST SECURITY SCHEMA:
    Validates incoming GraphQL signup requests with ruthless strictness.
    Now includes age-based routing requirements.
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

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Strictly checks for uppercase, lowercase, number, and special character."""
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        
        special_chars = "@$!%*?&_"
        if not any(c in special_chars for c in v):
            raise ValueError(f"Password must contain at least one special character from {special_chars}")
        
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
            raise ValueError("Invalid request payload.") 
        return v