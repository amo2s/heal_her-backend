"""
kids/ai_buddy/schemas/ai_buddy.py

The Fortified Data Contract Layer for the Kids AI Buddy.
Features: Security Shield Integration, XSS Sanitization, and Entropy Enforcement.
"""

import re
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
import nh3

# [UPDATE]: Security Shield Integration
# We alias our custom ValidationError to prevent collisions with Pydantic's internal core.
from core.exceptions import ValidationError as ShieldValidationError

# ---------------------------------------------------------
# Enums for Strict Type Enforcement
# ---------------------------------------------------------

class AIProvider(str, Enum):
    """
    Restricts the AI models strictly to the approved stack.
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
    [UPDATE]: Added model_config to forbid extra fields and auto-strip whitespace.
    """
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True
    )

    role: MessageRole
    content: str = Field(..., min_length=1, max_length=5000)

    @field_validator("content")
    @classmethod
    def sanitize_and_check_entropy(cls, v: str) -> str:
        """
        First line of defense. Strips HTML/scripts and prevents entropy attacks.
        [UPDATE]: Now uses the Security Shield for masked error reporting.
        """
        # 1. Strip all HTML tags to prevent XSS
        clean_text = nh3.clean(v, tags=set()) 
        
        if not clean_text.strip():
            # Internal message tracks the exact cause; Public remains supportive
            raise ShieldValidationError(
                public_message="I didn't quite catch that! Could you say it again?",
                internal_message="Validation Fail: Payload was empty or contained only HTML/JS."
            )

        # 2. Entropy/Repetition Check
        # Blocks massive repetitive strings (e.g., "aaaaa...") used in DoS or bypass attempts.
        if re.search(r'(.)\1{100,}', clean_text):
            raise ShieldValidationError(
                public_message="Whoops! That looks like a lot of the same letters. Let's try typing something else!",
                internal_message=f"Entropy Violation: Excessive repetitive characters detected from IP context."
            )

        return clean_text.strip()

class ChatRequest(BaseModel):
    """
    Incoming payload schema from the REST/Frontend layer.
    """
    model_config = ConfigDict(extra="forbid")

    session_id: Optional[str] = Field(
        default=None,
        description="The ID of the current chat session. None if it's a new conversation."
    )
    provider: AIProvider = Field(
        default=AIProvider.MISTRAL, 
        description="The target AI model for semantic routing."
    )
    # Strictly enforces context window limits
    history: List[Message] = Field(
        default_factory=list,
        max_length=10, 
        description="Previous conversation context."
    )
    current_message: Message

    @model_validator(mode='after')
    def validate_history_roles(self) -> 'ChatRequest':
        """
        [UPDATE]: Prevents System Prompt Injection attempts.
        """
        for msg in self.history:
            if msg.role == MessageRole.SYSTEM:
                raise ShieldValidationError(
                    public_message="Something went wrong with the chat history. Let's start fresh!",
                    internal_message="Security Violation: Attempted SYSTEM role injection in history array."
                )
        return self

# ---------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------

class ModelMetadata(BaseModel):
    """
    Tracks telemetry and billing metrics.
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
        Final pass to ensure the AI's response is safe for children's UI.
        """
        return nh3.clean(v, tags=set())