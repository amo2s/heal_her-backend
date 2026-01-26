from fastapi import HTTPException
from supabase import Client
from datetime import datetime, timezone

# --- CONFIGURATION ---
# Set this to how many messages a free user gets per day
DAILY_MSG_LIMIT = 50 

async def check_and_update_user_limit(user_id: str, supabase: Client):
    """
    1. Checks if the user has chatted today.
    2. Resets count if it's a new day (UTC).
    3. Blocks if limit reached (throws 402 Error).
    4. Increments count if safe.
    """
    
    # Get today's date in string format (YYYY-MM-DD)
    today_str = datetime.now(timezone.utc).date().isoformat()

    # 1. FETCH USAGE DATA
    try:
        response = supabase.table("user_daily_usage").select("*").eq("user_id", user_id).execute()
        data = response.data
    except Exception as e:
        print(f"DB Error (Usage Check): {e}")
        # If DB fails, we block to be safe
        raise HTTPException(status_code=500, detail="System check failed.")

    current_count = 0
    
    if data:
        record = data[0]
        db_date = record['last_active_date']
        current_count = record['message_count']

        # 2. CHECK IF NEW DAY (RESET LOGIC)
        if db_date != today_str:
            # It is a new day! Reset counter to 0
            current_count = 0
            # (The DB date will get updated in step 4)
    
    # 3. ENFORCE LIMIT
    if current_count >= DAILY_MSG_LIMIT:
        # 402 = Payment Required (Standard for "Quota Exceeded")
        raise HTTPException(
            status_code=402, 
            detail=f"Daily limit of {DAILY_MSG_LIMIT} messages reached."
        )

    # 4. INCREMENT & SAVE
    try:
        if data:
            # Update existing user's count and date
            supabase.table("user_daily_usage").update({
                "message_count": current_count + 1,
                "last_active_date": today_str
            }).eq("user_id", user_id).execute()
        else:
            # First time ever chatting -> Create record
            supabase.table("user_daily_usage").insert({
                "user_id": user_id, 
                "message_count": 1,
                "last_active_date": today_str
            }).execute()
            
    except Exception as e:
        print(f"Failed to update usage stats: {e}")

    # If we got here, they are allowed to chat
    return True