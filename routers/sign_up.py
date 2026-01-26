from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import supabase

# Create the router
router = APIRouter()

# Data Model (Matches your React Form)
class UserSignup(BaseModel):
    full_name: str
    email: str
    password: str

@router.post("/auth/signup")
async def signup(user_data: UserSignup):
    """
    Handles user registration. 
    Passes 'full_name' in metadata so the SQL Trigger can save it to 'profiles'.
    """
    try:
        # 1. Sign up with Supabase Auth
        # We pass 'full_name' inside 'options' -> 'data'
        response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": {
                    "full_name": user_data.full_name
                }
            }
        })

        # 2. Validation
        if not response.user:
            raise HTTPException(status_code=400, detail="Signup failed. Please check your input.")

        print(f"✅ New User: {user_data.email} | Name: {user_data.full_name}")

        return {
            "message": "Account created successfully.",
            "user_id": response.user.id,
            "email": response.user.email
        }

    except Exception as e:
        print(f"❌ Signup Error: {e}")
        # Send a clean error message to the frontend
        raise HTTPException(status_code=400, detail=str(e))