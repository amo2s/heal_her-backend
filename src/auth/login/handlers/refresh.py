import strawberry
from fastapi import HTTPException
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
        # 1. VERIFY THE REFRESH TOKEN
        # This will throw an exception if the token is expired or cryptographically invalid
        payload = verify_refresh_token(token)
        
        user_id = payload.get("sub")
        dashboard_segment = payload.get("dashboard") 
        
        if not user_id:
            raise ValueError("Token payload missing required subject identifier.")

        # 2. GENERATE NEW KEYS
        # We pass the extracted claims back into the new tokens
        token_data = {
            "sub": user_id, 
            "dashboard": dashboard_segment
        }
        
        new_access = create_access_token(data=token_data)
        new_refresh = create_refresh_token(data=token_data)
        
        # 3. RETURN TO PROXY
        return RefreshResponse(
            access_token=new_access,
            refresh_token=new_refresh
        )

    except Exception as e:
        # If the refresh token is dead, tampered with, or invalid, we reject it.
        # This triggers the Next.js proxy to wipe cookies and log the user out.
        raise Exception(f"Refresh validation failed: {str(e)}")