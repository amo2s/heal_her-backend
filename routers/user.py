from fastapi import APIRouter, Header, HTTPException, Depends
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# Initialize Supabase Client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Supabase credentials missing in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@router.get("/auth/me")
async def get_current_user(authorization: str = Header(None)):
    """
    1. Reads the 'Bearer <token>' from headers.
    2. Asks Supabase for the user's details.
    3. Returns the ID (for Chat) and Name (for Greeting).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No token provided")

    try:
        # Clean the token (Remove "Bearer " prefix if present)
        token = authorization.replace("Bearer ", "").strip()

        # Ask Supabase who this user is
        user_response = supabase.auth.get_user(token)
        user = user_response.user

        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Extract name from metadata (Saved during Sign Up)
        full_name = user.user_metadata.get("full_name", "Friend")
        
        # Logic: Get only the First Name (e.g., "Shulmmite" instead of "Shulmmite Jones")
        first_name = full_name.split(" ")[0]

        # --- CRITICAL: RETURN THE ID ---
        return {
            "id": user.id,          # <--- Frontend Chat needs this!
            "name": first_name,     # <--- Frontend Animation needs this!
            "full_name": full_name,
            "email": user.email
        }

    except Exception as e:
        print(f"Error fetching user: {e}")
        raise HTTPException(status_code=401, detail="Session expired")