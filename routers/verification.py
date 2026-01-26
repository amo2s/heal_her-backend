from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, WebSocket, WebSocketDisconnect
import shutil
import os
import time
import random
import threading
import asyncio
import json
from difflib import SequenceMatcher
from services.ai_gender import analyze_audio
from database import supabase
from dependencies import get_current_user
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

router = APIRouter(prefix="/verification", tags=["Verification"])

# --- CONFIGURATION ---
BASE_DIR = os.getcwd()
PENDING_DIR = os.path.join(BASE_DIR, "queue_pending")
PROCESSING_DIR = os.path.join(BASE_DIR, "queue_processing")
TEMP_DIR = os.path.join(BASE_DIR, "temp_uploads")

os.makedirs(PENDING_DIR, exist_ok=True)
os.makedirs(PROCESSING_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

raw_keys = [
    os.getenv("GROQ_API_KEY"),
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2")
]
GROQ_KEYS = [k for k in raw_keys if k]

if not GROQ_KEYS:
    print("⚠️ CRITICAL: No Groq API Keys found!")

CHALLENGES = [
    "The purple elephant flew over the Lagos bridge at midnight.",
    "Artificial intelligence is building a safer future for women everywhere.",
    "My voice is my unique biometric password and it verifies me.",
    "Technology should always serve humanity and protect the vulnerable.",
    "The quick brown fox jumped over the lazy dog in the winter snow.",
    "Heal Her is a digital sanctuary where safety comes first.",
    "I confirm that I am a living person recording this audio right now."
]

# --- 1. THE WORKER LOGIC (Unchanged - just updates DB) ---
def process_audio_file(filename):
    try:
        user_id = filename.split("_")[0]
        processing_path = os.path.join(PROCESSING_DIR, filename)
        
        print(f"⚙️ WORKER: Processing {filename}...")

        # 1. Run Heavy Math
        result = analyze_audio(processing_path)
        
        if result.get("error"):
            supabase.table("profiles").update({
                "verification_status": "error_analysis"
            }).eq("id", user_id).execute()
            return

        gender = result["gender"]
        confidence = result["confidence"]
        
        print(f"   ✅ Result: {gender.upper()} ({confidence:.2f})")

        # 2. DECISION LOGIC
        if gender == "female" and confidence > 0.85:
            # SUCCESS
            supabase.table("profiles").update({
                "is_verified": True,
                "verification_status": "approved"
            }).eq("id", user_id).execute()
            print(f"   🎉 User {user_id} VERIFIED!")

        elif gender == "male":
            # FAIL: MALE
            supabase.table("profiles").update({
                "is_verified": False,
                "verification_status": "rejected_male"
            }).eq("id", user_id).execute()
            print(f"   ❌ Rejected: Male Voice")

        else:
            # FAIL: UNCLEAR
            supabase.table("profiles").update({
                "is_verified": False,
                "verification_status": "rejected_unclear"
            }).eq("id", user_id).execute()
            print(f"   ❌ Rejected: Unclear/Low Confidence")

    except Exception as e:
        print(f"   ⚠️ Worker Error: {e}")
    finally:
        if os.path.exists(processing_path):
            os.remove(processing_path)

def worker_loop():
    print("👷 WORKER STARTED: Watching 'queue_pending' folder...")
    while True:
        try:
            files = os.listdir(PENDING_DIR)
            if not files:
                time.sleep(1)
                continue

            filename = files[0]
            pending_path = os.path.join(PENDING_DIR, filename)
            processing_path = os.path.join(PROCESSING_DIR, filename)

            try:
                shutil.move(pending_path, processing_path)
            except Exception:
                time.sleep(1)
                continue

            process_audio_file(filename)

        except Exception as e:
            print(f"⚠️ Worker Loop Error: {e}")
            time.sleep(1)

# Start Worker in Background
threading.Thread(target=worker_loop, daemon=True).start()


# --- 2. WEBSOCKET ENDPOINT (NEW!) ---
@router.websocket("/ws/verification")
async def websocket_endpoint(websocket: WebSocket):
    # 1. Accept Connection
    await websocket.accept()
    
    try:
        # 2. Extract Token from Query Params (ws://.../?token=XYZ)
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=1008)
            return

        # 3. Validate User (Manual Supabase Call since Depends doesn't work easily in WS)
        user = supabase.auth.get_user(token)
        if not user or not user.user:
            await websocket.close(code=1008)
            return
            
        user_id = user.user.id
        print(f"🔌 WS Connected: {user_id}")

        # 4. Monitoring Loop (Server-Side Polling)
        # We check the DB every 0.5s so the frontend doesn't have to.
        max_retries = 40  # 20 seconds max
        for _ in range(max_retries):
            
            # Fetch latest status
            response = supabase.table("profiles").select("verification_status").eq("id", user_id).single().execute()
            status = response.data.get("verification_status")

            if status == "approved":
                await websocket.send_json({"status": "success", "message": "Verification Successful"})
                return  # Close connection after success

            elif status == "rejected_male":
                await websocket.send_json({"status": "failed", "message": "Male voice detected"})
                return 

            elif status == "rejected_unclear":
                await websocket.send_json({"status": "failed", "message": "Voice unclear. Please try again."})
                return

            elif status == "rejected_phrase":
                await websocket.send_json({"status": "failed", "message": "Incorrect phrase."})
                return

            elif status == "error_analysis":
                await websocket.send_json({"status": "failed", "message": "AI Analysis failed."})
                return

            # Still processing... wait and loop again
            await asyncio.sleep(0.5)
        
        # If loop finishes without result
        await websocket.send_json({"status": "failed", "message": "Timeout"})

    except WebSocketDisconnect:
        print("🔌 WS Disconnected")
    except Exception as e:
        print(f"WS Error: {e}")
        try:
            await websocket.close()
        except:
            pass


# --- 3. STANDARD API ENDPOINTS ---
@router.get("/get-challenge")
async def get_challenge():
    phrase = random.choice(CHALLENGES)
    return {"phrase": phrase}

@router.post("/analyze-voice")
async def verify_voice(
    file: UploadFile = File(...), 
    expected_phrase: str = Form(...), 
    current_user: dict = Depends(get_current_user)
):
    if not file.filename.endswith((".wav", ".mp3", ".m4a", ".ogg")):
        raise HTTPException(status_code=400, detail="Invalid file format.")

    user_id = current_user.get("user_id")
    safe_filename = f"{user_id}_{int(time.time())}_{file.filename}"
    
    temp_path = os.path.join(TEMP_DIR, safe_filename)
    final_pending_path = os.path.join(PENDING_DIR, safe_filename)

    try:
        # 1. Reset Status to 'processing'
        supabase.table("profiles").update({
            "verification_status": "processing"
        }).eq("id", user_id).execute()

        # 2. Save File
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 3. Transcribe (Groq)
        detected_text = ""
        transcription_success = False
        
        for index, api_key in enumerate(GROQ_KEYS):
            try:
                client = Groq(api_key=api_key)
                with open(temp_path, "rb") as audio_file:
                    transcription = client.audio.transcriptions.create(
                        file=(file.filename, audio_file.read()),
                        model="whisper-large-v3-turbo", 
                        response_format="json",
                        language="en",
                        temperature=0.0
                    )
                detected_text = transcription.text.strip().lower()
                transcription_success = True
                break 
            except Exception as e:
                continue

        if not transcription_success:
            if os.path.exists(temp_path): os.remove(temp_path)
            supabase.table("profiles").update({"verification_status": "error_ai_busy"}).eq("id", user_id).execute()
            raise HTTPException(status_code=500, detail="AI Service Busy.")

        # 4. Check Phrase
        target_text = expected_phrase.strip().lower()
        similarity = SequenceMatcher(None, detected_text, target_text).ratio()
        
        if similarity < 0.4 and target_text not in detected_text:
            if os.path.exists(temp_path): os.remove(temp_path)
            
            # Update DB so WebSocket picks it up immediately
            supabase.table("profiles").update({"verification_status": "rejected_phrase"}).eq("id", user_id).execute()
            
            return {
                "status": "failed",
                "message": "Incorrect phrase.",
                "data": {"text_match": False}
            }

        # 5. Move to Worker Queue
        shutil.move(temp_path, final_pending_path)
        
        return {
            "status": "success", 
            "message": "Queued",
            "data": {"text_match": True}
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        print(f"Server Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Processing failed.")