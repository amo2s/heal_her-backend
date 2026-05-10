import jwt
from fastapi import Request, HTTPException, status
from datetime import datetime, timedelta, timezone
from core.config import settings

# =====================================================================
# THE CRYPTOGRAPHIC VAULT
# =====================================================================
# Allows for dual-key architecture if you define MANAGEMENT_JWT_SECRET_KEY in your .env
MANAGEMENT_SECRET = getattr(settings, "MANAGEMENT_JWT_SECRET_KEY", settings.JWT_SECRET_KEY)

def _get_secret(domain: str) -> str:
    """Routes the encryption to the correct cryptographic key based on the sector."""
    return MANAGEMENT_SECRET if domain == "management" else settings.JWT_SECRET_KEY

# =====================================================================
# TOKEN GENERATION (ISSUANCE)
# =====================================================================
def create_access_token(data: dict, domain: str):
    """
    Generates a short-lived access token strictly bound to a specific domain.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire, 
        "type": "access",
        "aud": domain  # THE EXTREMIST FIX: Binds token DNA to a specific dashboard
    })
    return jwt.encode(to_encode, _get_secret(domain), algorithm=settings.ALGORITHM)

def create_refresh_token(data: dict, domain: str):
    """Generates a long-lived refresh token strictly bound to a specific domain."""
    to_encode = data.copy()
    refresh_days = getattr(settings, 'REFRESH_TOKEN_EXPIRE_DAYS', 7)
    expire = datetime.now(timezone.utc) + timedelta(days=refresh_days)
    to_encode.update({
        "exp": expire, 
        "type": "refresh",
        "aud": domain
    })
    return jwt.encode(to_encode, _get_secret(domain), algorithm=settings.ALGORITHM)

# =====================================================================
# TOKEN EXTRACTION & VALIDATION (THE DETECTOR)
# =====================================================================
def verify_refresh_token(token: str, expected_domain: str):
    """Verifies the token, ensuring it hasn't been spoofed across domains."""
    try:
        payload = jwt.decode(
            token, 
            _get_secret(expected_domain), 
            algorithms=[settings.ALGORITHM],
            audience=expected_domain # Fails instantly if cross-domain spoofing occurs
        )
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type.")
        return payload
    except jwt.PyJWTError:
        return None

async def get_current_user_id(request: Request, expected_domain: str) -> str:
    """
    The Extraction Engine used by guards.py.
    Physically strips the token from the headers and aggressively validates its DNA.
    """
    auth_header = request.headers.get("Authorization")
    
    # 1. Structural Check
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Security Violation: Missing or Malformed Authorization Header."
        )
    
    token = auth_header.split(" ")[1]
    
    # 2. Cryptographic & Contextual Verification
    try:
        payload = jwt.decode(
            token, 
            _get_secret(expected_domain), 
            algorithms=[settings.ALGORITHM],
            audience=expected_domain 
        )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Security Violation: Token payload corrupted."
            )
        
        # 3. Typological Check
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Security Violation: Expected access token."
            )
            
        return str(user_id)
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session Expired: Token is no longer valid."
        )
    except jwt.InvalidAudienceError:
        # THE TRAP: Catches Kid -> Admin spoofing attempts
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-Domain Spoofing Blocked: Token does not belong to this sector."
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Security Violation: Token signature verification failed."
        )