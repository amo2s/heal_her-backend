from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from database import supabase

router = APIRouter()

# --- SECURITY SETUP ---
# This allows other files (like verification.py) to ask "Who is logged in?"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# --- DATA MODEL ---
class UserLogin(BaseModel):
    email: str
    password: str

# --- UTILITY: GET CURRENT USER ---
# This is the function verification.py imports!
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        # Ask Supabase who owns this token
        user = supabase.auth.get_user(token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Return the user object as a dictionary for easy access
        return {
            "user_id": user.user.id,
            "email": user.user.email
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

# --- LOGIN ENDPOINT ---
@router.post("/auth/login")
async def login(user_data: UserLogin):
    """
    1. Verify Email/Password with Supabase Auth.
    2. Fetch the 'is_verified' status from the 'profiles' table.
    3. Return Token + Verification Status.
    """
    try:
        # 1. Authenticate with Supabase (Check Password)
        auth_response = supabase.auth.sign_in_with_password({
            "email": user_data.email,
            "password": user_data.password,
        })

        if not auth_response.session:
            raise HTTPException(status_code=401, detail="Login failed.")

        user_id = auth_response.user.id

        # 2. Check Verification Status (The Gatekeeper)
        # We query the 'profiles' table to see if is_verified is True/False
        profile_response = supabase.table("profiles").select("is_verified, username").eq("id", user_id).execute()
        
        # Default to False if something is weird with the profile
        is_verified = False
        username = "User"
        
        if profile_response.data and len(profile_response.data) > 0:
            is_verified = profile_response.data[0].get("is_verified", False)
            username = profile_response.data[0].get("username", "User")

        print(f"🔑 User Logged In: {user_data.email} | Verified: {is_verified}")

        # 3. Return Critical Data
        return {
            "message": "Login successful",
            "access_token": auth_response.session.access_token,
            "refresh_token": auth_response.session.refresh_token,
            "user": {
                "id": user_id,
                "email": auth_response.user.email,
                "username": username,
                "is_verified": is_verified  # <--- FRONTEND NEEDS THIS
            }
        }

    except Exception as e:
        print(f"❌ Login Error: {str(e)}")
        # Provide a generic error to the user for security, but log the real one
        raise HTTPException(status_code=401, detail="Invalid email or password.")