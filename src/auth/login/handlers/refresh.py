import strawberry
from fastapi import HTTPException
from jose import jwt  # Using python-jose for JWT operations
from core.security import verify_refresh_token, create_access_token, create_refresh_token

@strawberry.type
class RefreshResponse:
    """
    The exact payload the Next.js proxy expects back.
    Strawberry auto-converts these to accessToken and refreshToken.
    """
    access_token: str
    refresh_token: str

async def handle_refresh(token: str) -> RefreshResponse:
    """
    Receives the 7-day token from the Next.js proxy and trades it for fresh keys.
    """
    try:
        # ---------------------------------------------------------
        # 1. PEEK AT THE DOMAIN (The Positional Argument Fix)
        # ---------------------------------------------------------
        # We must know the expected domain to satisfy the strict verifier.
        try:
            # [FIXED]: We use get_unverified_claims instead of decode. 
            # This completely bypasses the need for a 'key' argument while safely reading the payload.
            unverified_payload = jwt.get_unverified_claims(token)
            
            # Your system uses the 'role' (e.g., 'young_adult') as the security domain barrier
            security_domain = unverified_payload.get("role") 
            
            if not security_domain:
                 raise ValueError("Token missing critical domain/role routing claim.")
        except Exception as e:
            raise ValueError(f"Malformed token format: {str(e)}")

        # ---------------------------------------------------------
        # 2. STRICT VERIFICATION
        # ---------------------------------------------------------
        # We pass BOTH the token AND the domain to satisfy your Cross-Domain Spoofing fix
        payload = verify_refresh_token(token, security_domain)
        
        user_id = payload.get("sub")
        dashboard_segment = payload.get("dashboard") 
        
        if not user_id:
            raise ValueError("Token payload missing required subject identifier.")

        # ---------------------------------------------------------
        # 3. GENERATE NEW KEYS
        # ---------------------------------------------------------
        token_data = {
            "sub": user_id, 
            "role": security_domain,
            "dashboard": dashboard_segment
        }
        
        # THE FIX: Stamp the new tokens with the correct domain barrier!
        new_access = create_access_token(data=token_data, domain=security_domain)
        new_refresh = create_refresh_token(data=token_data, domain=security_domain)
        
        # ---------------------------------------------------------
        # 4. RETURN TO PROXY
        # ---------------------------------------------------------
        return RefreshResponse(
            access_token=new_access,
            refresh_token=new_refresh
        )

    except Exception as e:
        # If the refresh token is dead, tampered with, or invalid, we reject it.
        # This triggers the Next.js proxy to wipe cookies and log the user out.
        raise Exception(f"Refresh validation failed: {str(e)}")