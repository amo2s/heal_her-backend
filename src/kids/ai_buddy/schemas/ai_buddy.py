"""
schemas/ai_buddy.py

This module defines the strict data contracts and validation layers for the Kids AI Buddy.
It utilizes Pydantic v2 for data validation and nh3 for high-performance XSS sanitization.
"""

import re
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import nh3  # Must be installed: pip install nh3

# ---------------------------------------------------------
# Enums for Strict Type Enforcement
# ---------------------------------------------------------

class AIProvider(str, Enum):
    """
    Restricts the AI models strictly to the approved stack.
    Prevents injection of unauthorized or unauthenticated provider endpoints.
    """
    COHERE = "cohere"
    MISTRAL = "mistral"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"

class MessageRole(str, Enum):
    """
    Enforces standard conversational roles for LLM compatibility.
    """
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

# ---------------------------------------------------------
# Core Message Schemas
# ---------------------------------------------------------

class Message(BaseModel):
    """
    Represents a single conversational turn.
    Applies strict sanitization and validation to the content.
    """
    role: MessageRole
    # 5000 characters allows for extensive "safe space" expression (~1000 words)
    # while still preventing massive payload DOS attacks.
    content: str = Field(..., min_length=1, max_length=5000)

    @field_validator("content")
    @classmethod
    def sanitize_and_check_entropy(cls, v: str) -> str:
        """
        First line of defense. Strips all HTML/scripts and prevents buffer attacks.
        """
        # 1. Strip all HTML tags to prevent Cross-Site Scripting (XSS)
        clean_text = nh3.clean(v, tags=set()) 
        
        if not clean_text.strip():
            raise ValueError("Message content cannot be empty or solely HTML tags.")

        # 2. Entropy/Repetition Check
        # Prevents keyboard-mashing DOS attacks (e.g., "A" repeated 100 times)
        # Allows normal punctuation but blocks massive repetitive strings.
        if re.search(r'(.)\1{100,}', clean_text):
            raise ValueError("Message contains excessive repetitive characters and was flagged as spam.")

        return clean_text.strip()

class ChatRequest(BaseModel):
    """
    Incoming payload schema from the REST/Frontend layer.
    """
    # CRITICAL FIX: Added session_id so the handler doesn't crash looking for it.
    session_id: Optional[str] = Field(
        default=None,
        description="The ID of the current chat session. None if it's a new conversation."
    )
    provider: AIProvider = Field(
        default=AIProvider.MISTRAL, 
        description="The target AI model for semantic routing."
    )
    # Strictly enforces the "three former chat logs" + current message structure
    history: List[Message] = Field(
        default_factory=list,
        max_length=10, # Hard cap on history array size to prevent context overflow
        description="Previous conversation context."
    )
    current_message: Message

    @model_validator(mode='after')
    def validate_history_roles(self) -> 'ChatRequest':
        """
        Ensures the history array does not contain malformed or out-of-order roles 
        that could break the LLM prompt structure.
        """
        for msg in self.history:
            if msg.role == MessageRole.SYSTEM:
                raise ValueError("System prompts cannot be injected via the client history array.")
        return self

# ---------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------

class ModelMetadata(BaseModel):
    """
    Tracks telemetry and billing metrics for the specific model used.
    """
    provider_used: AIProvider
    tokens_consumed: int = Field(ge=0)
    latency_ms: float = Field(ge=0.0)
    safety_flag_triggered: bool = Field(default=False)

class ChatResponse(BaseModel):
    """
    Outgoing payload schema returned to the REST/Frontend layer.
    """
    role: MessageRole = Field(default=MessageRole.ASSISTANT)
    escaped_content: str
    metadata: ModelMetadata

    @field_validator("escaped_content")
    @classmethod
    def ensure_safe_output(cls, v: str) -> str:
        """
        Final pass to ensure the AI's response does not contain accidentally 
        hallucinated HTML or executable code before reaching the child's browser.
        """
        return nh3.clean(v, tags=set())