"""
kids/ai_buddy/services/ai_buddy.py

The Elite Core Service for the Kids AI Buddy.
Features: Dynamic Key Load Balancing, Application-Level Encryption, 
Async SSE Streaming, and External Persona Injection.
"""

import os
import re
import json
import itertools
import uuid
from collections import defaultdict
from typing import AsyncGenerator

from cryptography.fernet import Fernet
from litellm import acompletion
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Import configurations, models, and schemas
from core.config import settings
from kids.ai_buddy.models import ChatSession, ChatMessage
from kids.ai_buddy.schemas.ai_buddy import AIProvider, MessageRole

# IMPORT THE PERSONA ENGINE
from kids.ai_buddy.persona import analyze_sentiment_and_build_prompt

# ---------------------------------------------------------
# 1. APPLICATION-LEVEL ENCRYPTION ENGINE
# ---------------------------------------------------------
fernet_cipher = Fernet(settings.MESSAGE_ENCRYPTION_KEY.encode())

def encrypt_message(text: str) -> str:
    return fernet_cipher.encrypt(text.encode()).decode()

def decrypt_message(encrypted_text: str) -> str:
    return fernet_cipher.decrypt(encrypted_text.encode()).decode()


# ---------------------------------------------------------
# 2. DYNAMIC API KEY LOAD BALANCER
# ---------------------------------------------------------
class APIKeyManager:
    """
    Dynamically scans the environment for any API keys matching the pattern:
    PROVIDER_API_KEY_X (e.g., COHERE_API_KEY_1, GEMINI_API_KEY_99).
    """
    def __init__(self):
        self.pools = defaultdict(list)
        self.iterators = {}
        self._initialize_pools()

    def _initialize_pools(self):
        pattern = re.compile(r"^([A-Z]+)_API_KEY_(\d+)$")
        
        for env_key, env_val in os.environ.items():
            match = pattern.match(env_key)
            if match:
                provider = match.group(1).lower()
                self.pools[provider].append(env_val)
        
        for provider, keys in self.pools.items():
            if keys:
                self.iterators[provider] = itertools.cycle(keys)

    def get_key(self, provider: str) -> str:
        provider_key = provider.lower()
        if provider_key in self.iterators:
            return next(self.iterators[provider_key])
        
        fallback = os.getenv(f"{provider_key.upper()}_API_KEY")
        if not fallback:
            raise ValueError(f"CRITICAL: No API keys found for provider {provider}")
        return fallback

key_manager = APIKeyManager()


# ---------------------------------------------------------
# 3. BACKGROUND SUMMARIZATION WORKER
# ---------------------------------------------------------
async def generate_sidebar_title(session_id: str, first_message: str):
    """
    Runs in the background. Uses a cheap model to generate a 3-word title.
    """
    try:
        # CRITICAL: Import your database session maker here to get a fresh session.
        # Passing the main request 'db' into a background task causes crashes.
        from db import async_session_maker 
        
        key = key_manager.get_key("mistral")
        response = await acompletion(
            model="mistral/mistral-tiny",
            messages=[
                {"role": "system", "content": "Summarize this message in exactly 2 to 4 words. No punctuation."},
                {"role": "user", "content": first_message}
            ],
            api_key=key
        )
        title = response.choices[0].message.content.strip()

        # Use a fresh connection to avoid "Session already closed" errors
        async with async_session_maker() as db:
            session_record = await db.get(ChatSession, session_id)
            if session_record:
                session_record.title = title
                await db.commit()
            
    except Exception as e:
        print(f"[BACKGROUND WORKER ERROR] Failed to summarize title: {e}")


# ---------------------------------------------------------
# 4. THE MAIN SERVICE ORCHESTRATOR
# ---------------------------------------------------------
class AIBuddyService:
    @staticmethod
    async def process_chat_stream(
        user_id: str,
        session_id: str | None,
        raw_message: str,
        provider: AIProvider,
        db: AsyncSession,
        background_tasks: BackgroundTasks
    ) -> AsyncGenerator[str, None]:
        """
        The master pipeline. Handles context retrieval, dynamic persona injection, 
        load balancing, SSE streaming, and encrypted storage.
        """
        
        # --- FIX 1: PREVENT THE NEW CHAT 500 CRASH WITH DEFENSIVE COMMIT ---
        is_new_session = False
        if not session_id:
            session_id = str(uuid.uuid4())
            is_new_session = True
            new_session = ChatSession(
                id=session_id,
                user_id=user_id,
                title="New Buddy Talk ✨"
            )
            try:
                if db is not None:
                    db.add(new_session)
                    await db.commit()
            except Exception as e:
                print(f"[DB WARNING] Session created but DB commit delayed: {e}")
            
        # Step 1: Encrypt and safely save user message
        encrypted_user_msg = encrypt_message(raw_message)
        new_msg = ChatMessage(
            id=os.urandom(16).hex(),
            session_id=session_id,
            role=MessageRole.USER.value,
            encrypted_content=encrypted_user_msg
        )
        try:
            if db is not None:
                db.add(new_msg)
                await db.commit()
        except Exception as e:
            print(f"[DB WARNING] User message received but DB commit delayed: {e}")

        # Step 2: Context Retrieval
        try:
            result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(10)
            )
            history_records = result.scalars().all()[::-1]
        except Exception:
            history_records = [] # Fallback to empty history if DB is inaccessible

        # Step 3: Build Payload via Imported Persona Logic
        messages_payload = []
        system_prompt = analyze_sentiment_and_build_prompt(raw_message)
        messages_payload.append({"role": "system", "content": system_prompt})
        
        for record in history_records:
            decrypted_text = decrypt_message(record.encrypted_content)
            messages_payload.append({"role": record.role, "content": decrypted_text})

        # Step 4: Background Summarization
        if is_new_session:
            background_tasks.add_task(generate_sidebar_title, session_id, raw_message)

        # Step 5: Route to LLM
        active_key = key_manager.get_key(provider.value)
        model_map = {
            "cohere": "command-r",
            "mistral": "mistral/mistral-large-latest",
            "gemini": "gemini/gemini-1.5-pro",
            "deepseek": "deepseek/deepseek-chat"
        }
        target_model = model_map.get(provider.value, "mistral/mistral-large-latest")

        if is_new_session:
            yield f"data: {json.dumps({'session_id': session_id})}\n\n"

        # Step 6: SSE Stream
        full_ai_response = ""
        try:
            response_stream = await acompletion(
                model=target_model,
                messages=messages_payload,
                api_key=active_key,
                stream=True
            )
            
            async for chunk in response_stream:
                if chunk.choices[0].delta.content:
                    text_chunk = chunk.choices[0].delta.content
                    full_ai_response += text_chunk
                    yield f"data: {json.dumps({'content': text_chunk})}\n\n"
                    
        except Exception as e:
            print(f"[LLM STREAMING ERROR]: {e}")
            yield f"data: {json.dumps({'error': 'Buddy is taking a quick nap. Try again!'})}\n\n"
            return

        yield "data: [DONE]\n\n"

        # Step 7: The Bulletproof Database Save
        if full_ai_response:
            try:
                encrypted_ai_msg = encrypt_message(full_ai_response)
                ai_db_msg = ChatMessage(
                    id=os.urandom(16).hex(),
                    session_id=session_id,
                    role=MessageRole.ASSISTANT.value,
                    encrypted_content=encrypted_ai_msg,
                    provider_used=provider.value
                )
                
                # Check that DB connection is still perfectly alive before saving
                if db is not None:
                    db.add(ai_db_msg)
                    # Use a safely handled commit to prevent FastAPI lifespan crashes
                    commit_result = db.commit()
                    if commit_result is not None:
                        await commit_result
                        
            except Exception as db_err:
                # We catch the error silently here. The user ALREADY got their 
                # stream on the frontend, so we don't want to crash the whole server 
                # just because the database closed a microsecond too early.
                print(f"[SAFE FALLBACK] Stream finished successfully, but history save was interrupted: {db_err}")