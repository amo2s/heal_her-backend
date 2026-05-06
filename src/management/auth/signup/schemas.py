import re
import strawberry
from typing import Optional
from pydantic import BaseModel, ConfigDict

# =====================================================================
# 1. THE INGRESS FIREWALL (Strawberry Input)
# =====================================================================
@strawberry.input
class StaffSignUpInput:
    """
    The only data structure exposed to the GraphQL schema for signups.
    GraphQL inherently blocks undefined fields (acting as our strict perimeter).
    """
    full_name: str
    email: str
    password: str
    # THE HONEYPOT: Hidden on the frontend.
    website: Optional[str] = ""

    def validate_and_sanitize(self) -> "StaffSignUpInput":
        """
        The Cryptographic & Sanitization Engine.
        This must be called at the very beginning of the mutation resolver.
        """
        # 1. Whitespace Stripping & Normalization
        self.full_name = self.full_name.strip()
        self.email = self.email.strip().lower()

        # 2. Memory Exhaustion & Buffer Blocks (Length Limits)
        if not (2 <= len(self.full_name) <= 100):
            raise ValueError("Payload rejected: Invalid name length.")
        if len(self.email) > 255:
            raise ValueError("Payload rejected: Email exceeds maximum length.")
        if len(self.password) < 8 or len(self.password) > 128:
            raise ValueError("Payload rejected: Invalid password length.")

        # 3. Physical XSS & SQLi Block
        forbidden_chars = ["<", ">", "{", "}", "--", ";"]
        if any(char in self.full_name for char in forbidden_chars):
            raise ValueError("Payload rejected: Illegal characters detected.")
        if "script" in self.full_name.lower() or "drop" in self.full_name.lower():
            raise ValueError("Payload rejected: Suspicious pattern detected.")

        # 4. Military Cryptographic Complexity Enforcement
        pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_])'
        if not re.match(pattern, self.password):
            raise ValueError("Password fails minimum cryptographic complexity requirements.")

        return self

# =====================================================================
# 2. THE INTERNAL MUTATION (Air-Gapped Pydantic Model)
# =====================================================================
class StaffInternalCreateSchema(BaseModel):
    """
    Never exposed to the internet or GraphQL schema. 
    This strict Pydantic model is what the Service layer compiles and hands 
    to the Database after hashing the password.
    """
    model_config = ConfigDict(from_attributes=True)

    email: str
    full_name: str
    hashed_password: str
    signup_ip: Optional[str] = None
    signup_user_agent: Optional[str] = None

# =====================================================================
# 3. THE EGRESS FIREWALL (Strawberry Response)
# =====================================================================
@strawberry.type
class StaffSignUpResponse:
    """
    The only data permitted to leave the server after a signup attempt.
    Zero internal IDs, Zero status codes, Zero roles exposed.
    """
    message: str = "Application Submitted. The system administrator will review your credentials. You will receive an email once your access is provisioned."
    success: bool = True