from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

# 1. Import Tools
from routers.memory_manager import (
    create_session, 
    save_message, 
    get_chat_history, 
    get_user_sessions, 
    delete_session,
    update_session_title 
)
from routers.llm_clients import chat_with_ai
from routers.persona import HEAL_HER_PROMPT 

# --- NEW: IMPORT THE LOCKSMITH ---
from routers.crypto import encrypt_message, decrypt_message

# --- NEW: IMPORT THE LIMIT CHECKER ---
from services.user_limit_service import check_and_update_user_limit
from database import supabase

router = APIRouter()

class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None

# --- HELPER: DECRYPT HISTORY ---
def decrypt_history_list(history_list):
    """
    Helper function to unlock a whole list of messages 
    so the AI or User can read them.
    """
    decrypted_data = []
    for msg in history_list:
        # Create a copy so we don't mess up the original data
        clean_msg = msg.copy()
        clean_msg["content"] = decrypt_message(msg["content"])
        decrypted_data.append(clean_msg)
    return decrypted_data

# --- 1. MAIN CHAT ENDPOINT ---
@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # --- GUARD: VALIDATE USER ID ---
        if not request.user_id or request.user_id.strip() == "":
            print("⚠️ Request blocked: Missing User ID")
            raise HTTPException(status_code=400, detail="User ID is missing. Please log in.")

        # ==========================================
        # 🆕 NEW: CHECK DAILY LIMIT (The Gatekeeper)
        # ==========================================
        # This will throw a 402 error if the user has hit their daily limit.
        await check_and_update_user_limit(request.user_id, supabase)
        # ==========================================

        current_session_id = request.session_id
        is_new_session = False 

        # --- FIX: SANITIZE SESSION ID ---
        if current_session_id in ["null", "", "undefined"]:
            current_session_id = None

        # A. Handle Session Creation
        if not current_session_id:
            current_session_id = create_session(request.user_id, request.message)
            print(f"Created new session: {current_session_id}")
            is_new_session = True 

        # B. Save User Message (🔒 ENCRYPTED)
        # We lock the message BEFORE it touches the database.
        encrypted_user_msg = encrypt_message(request.message)
        save_message(current_session_id, "user", encrypted_user_msg)

        # C. Fetch Context (History)
        # The DB returns scrambled garbage. We must unlock it so the AI understands context.
        raw_history = get_chat_history(current_session_id)
        clean_history = decrypt_history_list(raw_history)
        
        # D. Inject Persona
        formatted_history = []
        # 1. System Prompt First
        formatted_history.append({"role": "system", "content": HEAL_HER_PROMPT})
        # 2. Chat History Next (Using the Decrypted/Clean Data)
        for msg in clean_history:
            formatted_history.append({"role": msg["role"], "content": msg["content"]})

        # E. Get AI Response
        # The AI reads the clean English text and generates a response.
        ai_response = await chat_with_ai(formatted_history)

        # F. Save AI Response (🔒 ENCRYPTED)
        # We lock the AI's reply immediately.
        encrypted_ai_msg = encrypt_message(ai_response)
        save_message(current_session_id, "assistant", encrypted_ai_msg)

        # --- G. SMART SUMMARIZATION ---
        # If this is the first message, generate a smart title
        if is_new_session:
            try:
                summary_prompt = [
                    {"role": "system", "content": "You are a smart summarizer. Create a very short title (max 4 words) for this user query. Do not use quotes."},
                    {"role": "user", "content": request.message}
                ]
                # Ask AI for the title
                smart_title = await chat_with_ai(summary_prompt)
                
                # Clean up the title (remove quotes if AI added them)
                clean_title = smart_title.strip().strip('"')
                
                # Update the database (We keep titles plain text for the sidebar UI)
                update_session_title(current_session_id, clean_title)
                print(f"📝 Auto-Summarized Title: {clean_title}")
                
            except Exception as e:
                print(f"⚠️ Summarization failed (using default): {e}")

        # H. Return
        # We return the PLAIN text to the user so they can see it immediately.
        return {
            "response": ai_response,
            "session_id": current_session_id
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 2. SIDEBAR: GET ALL SESSIONS ---
@router.get("/sessions")
async def get_sessions_endpoint(user_id: str):
    """
    Fetch all chat history for the sidebar list.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID required")
    try:
        sessions = get_user_sessions(user_id)
        return sessions
    except Exception as e:
        print(f"Error fetching sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 3. SIDEBAR: DELETE SESSION ---
@router.delete("/sessions/{session_id}")
async def delete_session_endpoint(session_id: str, user_id: str):
    """
    Delete a specific chat session.
    """
    try:
        delete_session(session_id, user_id)
        return {"status": "success", "message": "Session deleted"}
    except Exception as e:
        print(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 4. CHAT PAGE: LOAD HISTORY ---
@router.get("/history/{session_id}")
async def get_history_endpoint(session_id: str, user_id: str):
    """
    Download the message history for a specific session to show in the chat window.
    """
    try:
        # 1. Get Scrambled Data from DB
        raw_history = get_chat_history(session_id, limit=50)
        
        # 2. Unlock It (So the frontend displays real text)
        clean_history = decrypt_history_list(raw_history)
        
        return clean_history
    except Exception as e:
        print(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))