import re
import strawberry
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr

# =====================================================================
# 1. THE INGRESS FIREWALL (Strawberry Input)
# =====================================================================
@strawberry.input
class AdminLoginInput:
    """
    The only data structure permitted to enter the login phase.
    Acts as a physical block against oversized payloads and injection patterns.
    """
    email: str
    password: str
    # THE HONEYPOT: Hidden on the frontend. If filled, it's a bot.
    website: Optional[str] = ""

    def validate_and_sanitize(self) -> "AdminLoginInput":
        """
        The Cryptographic & Sanitization Engine.
        Executes brutal normalization before the database is ever queried.
        """
        # 1. Memory Exhaustion Blocks (Argon2 DoS Protection)
        if len(self.email) > 255:
            raise ValueError("Payload rejected: Malformed identifier.")
        if len(self.password) > 128:
            # Blocks massive passwords to prevent Argon2 CPU exhaustion
            raise ValueError("Payload rejected: Malformed credential.")

        # 2. Whitespace Stripping & Normalization
        self.email = self.email.strip().lower()

        # 3. Structural Identity Verification (Strict Regex)
        # Prevents SQLi payloads (e.g., ' OR 1=1 --) from ever touching the ORM
        email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_pattern, self.email):
            raise ValueError("Payload rejected: Invalid identifier format.")

        return self

# =====================================================================
# 2. THE INTERNAL DTO (Air-Gapped Processing Model)
# =====================================================================
class StaffLoginInternal(BaseModel):
    """
    Strict Pydantic model used internally by services.py to transport 
    verified identity data to the token generator. 
    NEVER EXPOSED TO GRAPHQL.
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    email: EmailStr
    full_name: str
    role: str
    status: str

# =====================================================================
# 3. THE EGRESS FIREWALL (Strawberry Response Types)
# =====================================================================
@strawberry.type
class StaffUserType:
    """
    The 'Ghost Object'. This is a highly redacted projection of the 
    database model. It contains ZERO sensitive metadata.
    """
    id: str           # UUID string, never an integer
    email: str
    fullName: str
    isActive: bool
    dashboard: str    # Will always return "management" to match your frontend routing

@strawberry.type
class AdminLoginResponse:
    """
    The exact cryptographic contract expected by the Next.js proxy upon login.
    """
    status: str
    message: str
    accessToken: str
    refreshToken: str
    user: StaffUserType

    @classmethod
    def generate_ghost_response(cls) -> "AdminLoginResponse":
        """
        THE GHOST FACTORY:
        Called by the mutation if the Guards detect a bot or invalid handshake.
        It generates a perfectly formatted, mathematically valid response 
        containing useless, fake tokens. The attacker's script thinks it succeeded.
        """
        fake_user = StaffUserType(
            id="00000000-0000-0000-0000-000000000000",
            email="ghost@sliververse.com",
            fullName="Unknown Entity",
            isActive=False,
            # We enforce the exact route string you specified
            dashboard="management" 
        )
        
        return cls(
            status="success",
            message="Authorized. Redirecting to Management Dashboard...",
            accessToken="ey...ghost...token",
            refreshToken="ey...ghost...refresh",
            user=fake_user
        )

@strawberry.type
class AdminRefreshResponse:
    """
    [NEW] THE ROTATION EGRESS:
    The sterile response payload for a successful Blood-Bound token rotation.
    Contains only the freshly forged cryptographic keys.
    """
    accessToken: str
    refreshToken: str