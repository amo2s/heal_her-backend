import re
from typing import Optional
import strawberry
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# ---------------------------------------------------------
# 1. THE PYDANTIC VAULT (Strict Validation Layer)
# ---------------------------------------------------------

class RequestOTPPayload(BaseModel):
    """validates the initial request to ensure only clean emails pass."""
    email: EmailStr = Field(..., description="The target email address.")


class VerifyOTPPayload(BaseModel):
    """locks down the OTP format to exactly 6 numeric digits. zero injection tolerance."""
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6, description="Exactly 6 digits.")

    @field_validator("otp_code")
    def validate_otp_format(cls, v):
        if not re.match(r"^\d{6}$", v):
            raise ValueError("OTP must be exactly 6 numeric digits.")
        return v


class ResetPasswordPayload(BaseModel):
    """enforces extreme password complexity and strictly matches the confirmation."""
    reset_token: str = Field(..., min_length=32, description="The secure token issued after OTP verification.")
    new_password: str = Field(..., min_length=8)
    confirm_password: str

    @field_validator("new_password")
    def validate_password_strength(cls, v):
        # x50 Enterprise standard: 1 Uppercase, 1 Lowercase, 1 Number, 1 Special
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character.")
        return v

    @model_validator(mode='after')
    def check_passwords_match(self) -> 'ResetPasswordPayload':
        if self.new_password != self.confirm_password:
            raise ValueError('Passwords do not match.')
        return self


# ---------------------------------------------------------
# 2. STRAWBERRY GRAPHQL CONTRACTS (Exposure Layer)
# ---------------------------------------------------------

@strawberry.input
class RequestOTPInput:
    email: str

@strawberry.input
class VerifyOTPInput:
    email: str
    otp_code: str

@strawberry.input
class ResetPasswordInput:
    reset_token: str
    new_password: str
    confirm_password: str

@strawberry.type
class StandardResetResponse:
    """
    Anti-Enumeration Shield. 
    Always returns the exact same success structure whether the email exists or not.
    """
    status: str = strawberry.field(description="Execution status (e.g., 'success' or 'error').")
    message: str = strawberry.field(description="Uniform response message.")

@strawberry.type
class VerifyOTPResponse:
    """
    Returns the secure reset token ONLY if the OTP is perfectly valid.
    """
    status: str
    message: str
    reset_token: Optional[str] = strawberry.field(
        default=None, 
        description="High-entropy short-lived token required for the final password change. Null if verification fails."
    )