"""
kids/ai_buddy/services/ai_buddy.py

The Fortified Core Service for the Kids AI Buddy.
Features: Security Shield Integration, Application-Level Encryption, 
Fail-Safe Background Summarization, and Resilient LLM Failover.
"""

import os
import re
import json
import itertools
import uuid
import logging
import inspect
from collections import defaultdict
from typing import AsyncGenerator

from cryptography.fernet import Fernet
from litellm import acompletion
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# [UPDATE]: Security Shield Integration
from core.exceptions import InfrastructureError, ValidationError
from core.config import settings

# Import models, schemas, and persona logic
from kids.ai_buddy.models import ChatSession, ChatMessage
from kids.ai_buddy.schemas.ai_buddy import AIProvider, MessageRole
from kids.ai_buddy.persona import analyze_sentiment_and_build_prompt

# Professional security logging
logger = logging.getLogger("HEAL_AI_SERVICE")

# ---------------------------------------------------------
# 1. APPLICATION-LEVEL ENCRYPTION ENGINE
# ---------------------------------------------------------
try:
    fernet_cipher = Fernet(settings.MESSAGE_ENCRYPTION_KEY.encode())
except Exception as e:
    logger.critical(f"ENCRYPTION KEY FAILURE: {str(e)}")

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
            raise InfrastructureError(
                internal_message=f"CRITICAL: No API keys found for provider {provider}"
            )
        return fallback

    def get_pool_size(self, provider: str) -> int:
        """Helper to determine max retry attempts per provider."""
        provider_key = provider.lower()
        if provider_key in self.pools:
            return len(self.pools[provider_key])
        if os.getenv(f"{provider_key.upper()}_API_KEY"):
            return 1
        return 0

key_manager = APIKeyManager()


# ---------------------------------------------------------
# 3. BACKGROUND SUMMARIZATION WORKER (Fortified)
# ---------------------------------------------------------
async def generate_sidebar_title(session_id: str, first_message: str):
    """
    Runs in the background. Uses a cheap model to generate a title.
    Includes error masking to prevent worker crashes from affecting the main thread.
    """
    try:
        from db import async_session_maker 
        
        key = key_manager.get_key("mistral")
        response = await acompletion(
            model="mistral/mistral-tiny",
            messages=[
                {"role": "system", "content": "Summarize into a concise 3-word title. No newlines. Return only string."},
                {"role": "user", "content": first_message}
            ],
            api_key=key
        )
        raw_title = response.choices[0].message.content.strip()
        safe_title = raw_title.replace("\n", " ").strip()[:100]

        async with async_session_maker() as db:
            session_record = await db.get(ChatSession, session_id)
            if session_record:
                session_record.title = safe_title
                await db.commit()
            
    except Exception as e:
        logger.error(f"[BACKGROUND WORKER] Title Generation Failed: {str(e)}")


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
        
        # Guard against malformed messages before hitting DB or LLM
        if not raw_message.strip():
            raise ValidationError(public_message="I can't hear you! What's on your mind?")

        # --- SESSION INITIALIZATION ---
        is_new_session = False
        if not session_id:
            session_id = str(uuid.uuid4())
            is_new_session = True
            new_session = ChatSession(id=session_id, user_id=user_id, title="New Buddy Talk ✨")
            db.add(new_session)

        # Encrypt and save user message
        encrypted_user_msg = encrypt_message(raw_message)
        new_msg = ChatMessage(
            id=os.urandom(16).hex(),
            session_id=session_id,
            role=MessageRole.USER.value,
            encrypted_content=encrypted_user_msg
        )
        db.add(new_msg)

        try:
            await db.commit()
        except Exception as e:
            raise InfrastructureError(internal_message=f"DB Session Init Failure: {str(e)}")

        # 2. Context Retrieval (Adaptive Execution)
        query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(10)
        )
        
        execute_result = db.execute(query)
        if inspect.isawaitable(execute_result):
            result = await execute_result
        else:
            result = execute_result
            
        history_records = result.scalars().all()[::-1]

        # 3. Build Persona Payload
        messages_payload = []
        system_prompt = analyze_sentiment_and_build_prompt(raw_message)
        messages_payload.append({"role": "system", "content": system_prompt})
        
        for record in history_records:
            decrypted_text = decrypt_message(record.encrypted_content)
            messages_payload.append({"role": record.role, "content": decrypted_text})

        # 4. Background Summarization
        if is_new_session:
            yield f"data: {json.dumps({'session_id': session_id})}\n\n"
            background_tasks.add_task(generate_sidebar_title, session_id, raw_message)

        # 5. Failover Architecture Setup
        model_map = {
            "cohere": "command-r",
            "mistral": "mistral/mistral-large-latest",
            "gemini": "gemini/gemini-1.5-pro",
            "deepseek": "deepseek/deepseek-chat"
        }

        # Build sequence prioritizing the user's requested provider, then falling back
        fallback_sequence = [provider.value] + [p for p in model_map.keys() if p != provider.value]
        
        full_ai_response = ""
        stream_successful = False
        successful_provider = provider.value

        # 6. Execution Loop (Cross-Provider Dynamic Fallback)
        for current_provider in fallback_sequence:
            if stream_successful:
                break

            target_model = model_map.get(current_provider)
            pool_size = key_manager.get_pool_size(current_provider)

            if pool_size == 0:
                continue

            # Intra-Provider Key Rotation
            for attempt in range(pool_size):
                try:
                    active_key = key_manager.get_key(current_provider)

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
                    
                    stream_successful = True
                    successful_provider = current_provider
                    break  # Circuit closed: exit rotation loop

                except Exception as e:
                    logger.warning(
                        f"[{current_provider.upper()} API ERROR] Attempt {attempt + 1}/{pool_size} failed: {str(e)}"
                    )
                    continue  # Intercept failure and cycle key

        # 7. Total Infrastructure Outage Handling
        if not stream_successful:
            logger.error("[LLM ERROR] All providers and keys exhausted for Kids AI Buddy.")
            yield f"data: {json.dumps({'error': 'Buddy is having trouble connecting. Try again in a little bit!'})}\n\n"
            return

        yield "data: [DONE]\n\n"

        # 8. Persistent Storage for AI Response (Adaptive Update)
        if full_ai_response:
            try:
                encrypted_ai_msg = encrypt_message(full_ai_response)
                ai_db_msg = ChatMessage(
                    id=os.urandom(16).hex(),
                    session_id=session_id,
                    role=MessageRole.ASSISTANT.value,
                    encrypted_content=encrypted_ai_msg,
                    provider_used=successful_provider
                )
                
                if db is not None:
                    db.add(ai_db_msg)
                    commit_result = db.commit()
                    if commit_result is not None:
                        await commit_result
                        
            except Exception as db_err:
                logger.error(f"[SAVE DELAY] Stream finished but history save interrupted: {str(db_err)}")