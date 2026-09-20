"""
src/young_adult/heal_ai/services/heal_ai.py

The Fortified Core Service for Young Adult Heal AI.
Features: Security Shield Integration, Adaptive DB Execution, 
Zero-Leak Infrastructure Fail-Safes, and Resilient LLM Failover.
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

# [UPDATE]: Security Shield & Architectural Imports
from core.config import settings
from core.exceptions import InfrastructureError, ValidationError
from young_adult.heal_ai.models import YoungAdultChatSession, YoungAdultChatMessage
from young_adult.heal_ai.schemas import AIProvider, MessageRole

# IMPORT THE YOUNG ADULT PERSONA ENGINE
from young_adult.heal_ai.persona import analyze_sentiment_and_build_prompt

# Professional Logger
logger = logging.getLogger("HEAL_YOUNG_ADULT_SERVICE")

# ---------------------------------------------------------
# 1. APPLICATION-LEVEL ENCRYPTION ENGINE
# ---------------------------------------------------------
try:
    fernet_cipher = Fernet(settings.MESSAGE_ENCRYPTION_KEY.encode())
except Exception as e:
    logger.critical(f"YOUNG ADULT ENCRYPTION KEY FAILURE: {str(e)}")

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
    PROVIDER_API_KEY_X (e.g., MISTRAL_API_KEY_1, GEMINI_API_KEY_2).
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
# 3. BACKGROUND SUMMARIZATION WORKER
# ---------------------------------------------------------
async def generate_sidebar_title(session_id: str, first_message: str):
    """
    Runs in the background to generate a professional session title.
    Includes hard truncation to prevent database schema violations.
    """
    try:
        from db import async_session_maker 
        
        key = key_manager.get_key("mistral")
        response = await acompletion(
            model="mistral/mistral-tiny",
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "Summarize this request into a highly concise professional title. "
                        "MAXIMUM 5 words. MAXIMUM 50 characters. NO NEWLINES. "
                        "Return ONLY the title string, nothing else."
                    )
                },
                {"role": "user", "content": first_message}
            ],
            api_key=key
        )
        raw_title = response.choices[0].message.content.strip()

        # Sanitization & Hard Truncation
        safe_title = raw_title.replace("\n", " ").strip()[:100]

        async with async_session_maker() as db:
            session_record = await db.get(YoungAdultChatSession, session_id)
            if session_record:
                session_record.title = safe_title
                await db.commit()
            
    except Exception as e:
        logger.error(f"[WORKER ERROR] Failed to summarize young adult session title: {str(e)}")


# ---------------------------------------------------------
# 4. THE MAIN SERVICE ORCHESTRATOR
# ---------------------------------------------------------
class HealAIService:
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
        The Master Pipeline for Young Adult Heal AI.
        Integrated with Resilient State-Aware Failover and Cross-Provider Hot-Swapping.
        """
        
        if not raw_message.strip():
            raise ValidationError(public_message="I'm here to listen. What's on your mind?")

        # --- SESSION INITIALIZATION ---
        is_new_session = False
        if not session_id:
            session_id = str(uuid.uuid4())
            is_new_session = True
            new_session = YoungAdultChatSession(
                id=session_id,
                user_id=user_id,
                title="Heal AI Session"
            )
            db.add(new_session)

        # 1. Encrypt and store user input
        encrypted_user_msg = encrypt_message(raw_message)
        new_msg = YoungAdultChatMessage(
            id=os.urandom(16).hex(),
            session_id=session_id,
            role=MessageRole.USER.value,
            encrypted_content=encrypted_user_msg
        )
        db.add(new_msg)

        try:
            await db.commit()
        except Exception as e:
            raise InfrastructureError(internal_message=f"Young Adult DB Session Init Failure: {str(e)}")

        # 2. Context Retrieval
        query = (
            select(YoungAdultChatMessage)
            .where(YoungAdultChatMessage.session_id == session_id)
            .order_by(YoungAdultChatMessage.created_at.desc())
            .limit(15)
        )
        
        execute_result = db.execute(query)
        if inspect.isawaitable(execute_result):
            result = await execute_result
        else:
            result = execute_result
            
        history_records = result.scalars().all()[::-1]

        # 3. Build Payload
        messages_payload = []
        system_prompt = analyze_sentiment_and_build_prompt(raw_message)
        messages_payload.append({"role": "system", "content": system_prompt})
        
        for record in history_records:
            decrypted_text = decrypt_message(record.encrypted_content)
            messages_payload.append({"role": record.role, "content": decrypted_text})

        # 4. Background Summarization
        if is_new_session:
            background_tasks.add_task(generate_sidebar_title, session_id, raw_message)
            yield f"data: {json.dumps({'session_id': session_id})}\n\n"

        # 5. Failover Architecture Setup
        model_map = {
            "cohere": "command-r-plus",
            "mistral": "mistral/mistral-large-latest",
            "gemini": "gemini/gemini-1.5-pro",
            "deepseek": "deepseek/deepseek-chat"
        }

        # Build sequence prioritizing the user's selected provider, then falling back to others
        fallback_sequence = [provider.value] + [p for p in model_map.keys() if p != provider.value]
        
        full_ai_response = ""
        stream_successful = False
        successful_provider = provider.value

        # 6. Execution Loop (Option 2: Cross-Provider)
        for current_provider in fallback_sequence:
            if stream_successful:
                break

            target_model = model_map.get(current_provider)
            pool_size = key_manager.get_pool_size(current_provider)
            
            if pool_size == 0:
                continue

            # (Option 1: Intra-Provider Key Rotation)
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
                    break  # Circuit closed: exit key rotation loop

                except Exception as e:
                    logger.warning(f"[{current_provider.upper()} API ERROR] Attempt {attempt + 1}/{pool_size} failed: {str(e)}")
                    continue  # Circuit tripped: try next key in pool
                    
        # 7. Total Infrastructure Failure Handling
        if not stream_successful:
            logger.error("[LLM ERROR] All providers and keys exhausted. Total failover triggered.")
            yield f"data: {json.dumps({'error': 'Heal AI encountered a critical network disruption. Please retry later.'})}\n\n"
            return

        yield "data: [DONE]\n\n"

        # 8. Persistent Storage for AI Response
        if full_ai_response:
            try:
                encrypted_ai_msg = encrypt_message(full_ai_response)
                ai_db_msg = YoungAdultChatMessage(
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
                logger.error(f"[DB] Final history save failed: {str(db_err)}")