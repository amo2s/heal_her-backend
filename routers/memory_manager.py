import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# 1. Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
# Using ANON_KEY as requested
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY") 

if not SUPABASE_URL or not SUPABASE_KEY:
    print("CRITICAL ERROR: Supabase keys are missing from .env")

# Initialize the client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Function to Create a New Session (Start a conversation)
def create_session(user_id: str, first_message: str):
    # Auto-generate a title from the first few words
    short_title = first_message[:30] + "..."
    
    # Insert new session
    response = supabase.table("chat_sessions").insert({
        "user_id": user_id,
        "title": short_title
    }).execute()
    
    # Return the new Session ID safely
    if response.data:
        return response.data[0]['id']
    else:
        raise Exception("Failed to create session: No data returned")

# 3. Function to Save a Message (User or AI)
def save_message(session_id: str, role: str, content: str):
    supabase.table("chat_messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content
    }).execute()

# 4. Function to Get History (For Context)
def get_chat_history(session_id: str, limit: int = 10):
    # Get the last 'limit' messages to send to the AI
    response = supabase.table("chat_messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()
    
    # Reverse them so they are in chronological order (Oldest -> Newest)
    messages = response.data
    return messages[::-1]

# 5. NEW: Get All Sessions for a User (For Sidebar)
def get_user_sessions(user_id: str):
    response = supabase.table("chat_sessions")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("created_at", desc=True)\
        .execute()
    
    return response.data

# 6. NEW: Delete a Session
def delete_session(session_id: str, user_id: str):
    # Security: Ensure we only delete if the user owns the session
    supabase.table("chat_sessions")\
        .delete()\
        .eq("id", session_id)\
        .eq("user_id", user_id)\
        .execute()
    
    # 7. NEW: Update a Session Title
def update_session_title(session_id: str, new_title: str):
    supabase.table("chat_sessions")\
        .update({"title": new_title})\
        .eq("id", session_id)\
        .execute()