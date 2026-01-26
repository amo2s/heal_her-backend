# main.py
import static_ffmpeg
static_ffmpeg.add_paths()

import socketio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
import os
import threading
import asyncio

# --- ROUTER IMPORTS ---
from routers import sign_up, login, user, profiles, verification 
from routers.chat_routes import router as chat_router 
from database import supabase

# --- SERVICE IMPORTS ---
# This handles the Guest Chat (3 messages limit)
from services.guest_service import process_guest_chat

# --- SOCKET.IO SETUP ---
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n--- 🏥 Heal Her System Startup (Socket.IO Mode) ---")
    
    # 1. Start Verification Worker (if needed)
    try:
        print("👷 Starting Verification Background Worker...")
        worker_thread = threading.Thread(target=verification.worker_loop, daemon=True)
        worker_thread.start()
        print("✅ Verification Worker Active")
    except Exception as e:
        print(f"❌ Failed to start worker: {e}")

    yield
    print("--- System Shutdown ---")

# --- FASTAPI SETUP ---
app = FastAPI(title="Heal Her - Auth Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MOUNT SOCKET.IO ---
combined_app = socketio.ASGIApp(sio, other_asgi_app=app)

# --- REGISTER ROUTERS ---
app.include_router(sign_up.router)
app.include_router(login.router)
app.include_router(user.router)      
app.include_router(profiles.router)
app.include_router(verification.router) 
# The Chat Router (Handles Signed-In Users + Daily Limit of 50)
app.include_router(chat_router)      

# --- GUEST CHAT ENDPOINT ---
# (Handles Anonymous Users + Total Limit of 3)
class GuestChatRequest(BaseModel):
    fingerprint: str
    message: str

@app.post("/guest-chat")
async def guest_chat_endpoint(request: GuestChatRequest):
    return await process_guest_chat(request.fingerprint, request.message, supabase)


# --- SOCKET.IO EVENTS ---

@sio.event
async def connect(sid, environ, auth):
    """
    Called when frontend connects: socket = io(url, { auth: { token: '...' } })
    """
    print(f"🔌 Socket Connected: {sid}")
    
    token = auth.get("token") if auth else None
    
    if not token:
        print(f"❌ No token provided for {sid}, disconnecting...")
        await sio.disconnect(sid)
        return

    # Verify User with Supabase
    user = supabase.auth.get_user(token)
    if not user or not user.user:
        print(f"❌ Invalid token for {sid}, disconnecting...")
        await sio.disconnect(sid)
        return

    user_id = user.user.id
    print(f"✅ User {user_id} authenticated on socket {sid}")
    
    await sio.save_session(sid, {'user_id': user_id})

    # Start Monitoring Verification Status
    asyncio.create_task(monitor_verification_status(sid, user_id))

@sio.event
async def disconnect(sid):
    print(f"🔌 Socket Disconnected: {sid}")

async def monitor_verification_status(sid, user_id):
    """
    Checks DB every 0.5s and emits event to frontend if status changes.
    """
    print(f"👀 Monitoring started for {user_id}")
    max_retries = 40 # 20 seconds
    
    for _ in range(max_retries):
        try:
            response = supabase.table("profiles").select("verification_status").eq("id", user_id).single().execute()
            status = response.data.get("verification_status")

            if status == "approved":
                await sio.emit("verification_result", {"status": "success", "message": "Verified!"}, room=sid)
                return

            elif status == "rejected_male":
                await sio.emit("verification_result", {"status": "failed", "message": "Male voice detected"}, room=sid)
                return 

            elif status == "rejected_phrase":
                await sio.emit("verification_result", {"status": "failed", "message": "Incorrect phrase."}, room=sid)
                return
            
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"Monitor Error: {e}")
            break
            
    await sio.emit("verification_result", {"status": "failed", "message": "Timeout"}, room=sid)