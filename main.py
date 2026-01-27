import static_ffmpeg
static_ffmpeg.add_paths()

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
import threading
import asyncio
import urllib.parse  # <--- REQUIRED for parsing Socket.IO query strings

# --- ROUTER IMPORTS ---
from routers import sign_up, login, user, profiles, verification 
from routers.chat_routes import router as chat_router 
from database import supabase

# --- SERVICE IMPORTS ---
from services.guest_service import process_guest_chat

# --- 1. GLOBAL TRUSTED LIST (For HTTP API) ---
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://heal-her.vercel.app",
    "https://www.heal-her.vercel.app"
]

# --- 2. SOCKET.IO SETUP ---
# cors_allowed_origins="*" is CRITICAL here to stop the 403 error.
sio = socketio.AsyncServer(
    async_mode='asgi', 
    cors_allowed_origins="*" 
)

# --- 3. LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n--- 🏥 Heal Her System Startup ---")
    try:
        worker_thread = threading.Thread(target=verification.worker_loop, daemon=True)
        worker_thread.start()
        print("✅ Verification Worker Active")
    except Exception as e:
        print(f"❌ Worker Error: {e}")
    yield

# --- 4. FASTAPI SETUP ---
app = FastAPI(title="Heal Her - Auth Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 🟢 HEALTH CHECK ---
@app.api_route("/", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "active", "message": "Heal Her Backend is Running 🏥"}

# --- 5. MOUNT SOCKET.IO ---
# Wraps the FastAPI app so Socket.IO catches requests first
combined_app = socketio.ASGIApp(
    socketio_server=sio, 
    other_asgi_app=app,
    socketio_path="/socket.io/"
)

# --- REGISTER ROUTERS ---
app.include_router(sign_up.router)
app.include_router(login.router)
app.include_router(user.router)      
app.include_router(profiles.router)
app.include_router(verification.router) 
app.include_router(chat_router)       

# --- GUEST CHAT ---
class GuestChatRequest(BaseModel):
    fingerprint: str
    message: str

@app.post("/guest-chat")
async def guest_chat_endpoint(request: GuestChatRequest):
    return await process_guest_chat(request.fingerprint, request.message, supabase)

# --- 6. SOCKET.IO EVENTS (Fixed Logic) ---
@sio.event
async def connect(sid, environ, auth):
    print(f"🔌 Socket Connection Attempt: {sid}")
    
    token = None
    
    # METHOD A: Check 'auth' object (Standard Socket.IO)
    if auth and "token" in auth:
        token = auth["token"]
    
    # METHOD B: Check Query String (Fallback)
    # This is what was missing! Socket.IO often puts the token here.
    if not token:
        try:
            query_string = environ.get('QUERY_STRING', '')
            params = urllib.parse.parse_qs(query_string)
            if 'token' in params:
                token = params['token'][0]
        except Exception:
            pass

    # If we still have no token, REJECT the connection.
    if not token:
        print(f"❌ Access Denied: No token found for {sid}")
        return False  # This sends the 403 Forbidden

    # Verify User with Supabase
    try:
        res = supabase.auth.get_user(token)
        if not res or not res.user:
            print(f"❌ Access Denied: Invalid/Expired token for {sid}")
            return False
        
        user_id = res.user.id
        print(f"✅ User {user_id} authenticated on {sid}")
        
        # Save session
        await sio.save_session(sid, {'user_id': user_id})
        
        # Start the background monitor for this user
        asyncio.create_task(monitor_verification_status(sid, user_id))
        
        return True # Connection Successful
        
    except Exception as e:
        print(f"❌ Auth Exception: {e}")
        return False

@sio.event
async def disconnect(sid):
    print(f"🔌 Socket Disconnected: {sid}")

async def monitor_verification_status(sid, user_id):
    """
    Polls the database for status updates and pushes them to the client.
    """
    max_retries = 60 # 30 seconds timeout
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
                await sio.emit("verification_result", {"status": "failed", "message": "Incorrect phrase"}, room=sid)
                return
            
            await asyncio.sleep(0.5)
        except Exception:
            await asyncio.sleep(0.5)
            
    await sio.emit("verification_result", {"status": "failed", "message": "Timeout"}, room=sid)