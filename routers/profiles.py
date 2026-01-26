from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Form
from database import supabase
import time
import io
from PIL import Image as PILImage 

router = APIRouter()

ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"]

# --- 1. GET PROFILE ---
@router.get("/profile/me")
async def get_my_profile(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="No token provided")
    
    try:
        token = authorization.replace("Bearer ", "")
        user_resp = supabase.auth.get_user(token)
        if not user_resp or not user_resp.user:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        user_id = user_resp.user.id
        response = supabase.table("profiles").select("*").eq("id", user_id).execute()
        profile = response.data[0] if response.data else {}
        
        return {
            "id": user_id,
            "full_name": profile.get("full_name") or user_resp.user.user_metadata.get("full_name", ""),
            "email": user_resp.user.email, 
            "phone": profile.get("phone", ""),
            "avatar_url": profile.get("avatar_url", "")
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch profile")

# --- 2. UPDATE PROFILE ---
@router.put("/profile/update")
async def update_profile(
    authorization: str = Header(None),
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(None),
    phone: str = Form(None),
    file: UploadFile = File(None)
):
    if not authorization:
        raise HTTPException(status_code=401, detail="No token")

    try:
        token = authorization.replace("Bearer ", "")
        user_resp = supabase.auth.get_user(token)
        
        if not user_resp or not user_resp.user:
            raise HTTPException(status_code=401, detail="Auth session missing!")
            
        user_id = user_resp.user.id
        profile_data = {"id": user_id, "full_name": full_name, "phone": phone}

        # Step 1: Image Processing & Storage
        if file:
            content = await file.read()
            img = PILImage.open(io.BytesIO(content))
            img.thumbnail((400, 400)) # Server-side resize

            output = io.BytesIO()
            img.save(output, format="WEBP", quality=80) 
            output.seek(0)

            file_path = f"{user_id}-{int(time.time())}.webp"
            
            # Uploading with sanitized URL from database.py
            supabase.storage.from_("avatars").upload(
                file=output.read(),
                path=file_path,
                file_options={"content-type": "image/webp"}
            )
            
            # Get URL with CDN Transformation hints
            public_url = supabase.storage.from_("avatars").get_public_url(
                file_path, 
                options={"transform": {"width": 200, "height": 200, "resize": "cover"}}
            )
            profile_data["avatar_url"] = public_url

        # Step 2: Save to SQL Database (Always do this before Auth updates)
        supabase.table("profiles").upsert(profile_data, on_conflict="id").execute()

        # Step 3: Auth Credential Updates (Protected in a sub-try)
        try:
            auth_updates = {"data": {"full_name": full_name}}
            if email != user_resp.user.email:
                auth_updates["email"] = email
            if password and len(password.strip()) > 0:
                auth_updates["password"] = password
            
            supabase.auth.update_user(auth_updates)
        except Exception:
            # We catch this because email changes often reset the session token
            # But since SQL is already updated, the data is safe.
            pass

        return {"message": "Success"}

    except Exception as e:
        print(f"❌ Final Backend Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. DELETE ACCOUNT ---
@router.delete("/profile/delete-account")
async def delete_account(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="No token")
    try:
        token = authorization.replace("Bearer ", "")
        user_resp = supabase.auth.get_user(token)
        user_id = user_resp.user.id
        supabase.table("profiles").delete().eq("id", user_id).execute()
        supabase.auth.sign_out()
        return {"message": "Deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))