from fastapi import HTTPException
from supabase import Client

# --- IMPORT YOUR ACTUAL AI LOGIC ---
from routers.llm_clients import chat_with_ai
from routers.persona import HEAL_HER_PROMPT

async def process_guest_chat(fingerprint: str, message: str, supabase: Client):
    """
    Handles the logic for guest chatting:
    1. Checks rate limit in Supabase.
    2. Generates AI response using the real Heal Her model.
    3. Updates usage count.
    """
    
    # 1. CHECK DATABASE FOR FINGERPRINT
    try:
        response = supabase.table("guest_usage").select("*").eq("fingerprint", fingerprint).execute()
        data = response.data
    except Exception as e:
        print(f"DB Error: {e}")
        # Fail safe: If DB is down, we block to prevent abuse, or you could allow pass-through.
        raise HTTPException(status_code=500, detail="System check failed.")

    current_count = 0
    if data:
        current_count = data[0]['message_count']
    
    # 2. ENFORCE LIMIT (BLOCK IF >= 3)
    if current_count >= 3:
        raise HTTPException(status_code=403, detail="Guest limit reached. Please login.")

    # 3. GENERATE AI RESPONSE (REAL AI)
    try:
        # We construct a stateless context for the guest.
        # Since we don't save guest history, we send: System Prompt + Current Message.
        formatted_history = [
            {"role": "system", "content": HEAL_HER_PROMPT},
            {"role": "user", "content": message}
        ]

        # Call your existing AI router
        ai_reply = await chat_with_ai(formatted_history)
        
    except Exception as e:
        print(f"AI Generation Error: {e}")
        raise HTTPException(status_code=500, detail="AI Service unavailable.")

    # 4. UPDATE DATABASE (INCREMENT COUNT)
    try:
        if data:
            # Update existing user count
            supabase.table("guest_usage").update({"message_count": current_count + 1}).eq("fingerprint", fingerprint).execute()
        else:
            # Insert new guest user
            supabase.table("guest_usage").insert({"fingerprint": fingerprint, "message_count": 1}).execute()
            
    except Exception as e:
        print(f"DB Update Error: {e}")
        # We don't stop the response if logging fails, but we print the error.

    return {"response": ai_reply}