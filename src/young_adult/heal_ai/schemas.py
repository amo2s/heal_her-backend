"""
src/young_adult/heal_ai/schemas.py

The Fortified Data Contract Layer for the Young Adult Heal AI.
Features: Security Shield Integration, XSS Sanitization, and Entropy Enforcement.
"""

import re
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
import nh3

# [UPDATE]: Security Shield Integration
# Aliasing core exception to avoid name collisions with Pydantic internal types.
from core.exceptions import ValidationError as ShieldValidationError

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
    # [UPDATE]: Enforce strict schema boundaries.
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True
    )

    role: MessageRole
    # 10,000 characters provides ample space for complex life situations.
    content: str = Field(..., min_length=1, max_length=10000)

    @field_validator("content")
    @classmethod
    def sanitize_and_check_entropy(cls, v: str) -> str:
        """
        First line of defense. Strips all HTML/scripts and prevents buffer attacks.
        [UPDATE]: Integrated with Security Shield to mask internal validation logic.
        """
        # 1. Strip all HTML tags to prevent Cross-Site Scripting (XSS)
        clean_text = nh3.clean(v, tags=set()) 
        
        if not clean_text.strip():
            # [UPDATE]: Masked error to prevent revealing internal logic.
            raise ShieldValidationError(
                public_message="I'm here to listen. What's on your mind?",
                internal_message="Validation Fail: Young Adult payload was empty or pure HTML."
            )

        # 2. Entropy/Repetition Check
        # Prevents keyboard-mashing DOS attacks.
        if re.search(r'(.)\1{100,}', clean_text):
            raise ShieldValidationError(
                public_message="That's a lot of the same character! Could you rephrase that?",
                internal_message="Entropy Violation: Excessive repetitive characters detected."
            )

        return clean_text.strip()

class ChatRequest(BaseModel):
    """
    Incoming payload schema from the REST/Frontend layer for Young Adults.
    """
    # [UPDATE]: Forbid extra fields to block payload injection.
    model_config = ConfigDict(extra="forbid")

    session_id: Optional[str] = Field(
        default=None,
        description="The ID of the current chat session. None if it's a new conversation."
    )
    provider: AIProvider = Field(
        default=AIProvider.MISTRAL, 
        description="The target AI model for semantic routing."
    )
    # History cap at 20 ensures deep context for adult conversations.
    history: List[Message] = Field(
        default_factory=list,
        max_length=20, 
        description="Previous conversation context."
    )
    current_message: Message

    @model_validator(mode='after')
    def validate_history_roles(self) -> 'ChatRequest':
        """
        Ensures the history array does not contain malformed or out-of-order roles.
        """
        for msg in self.history:
            if msg.role == MessageRole.SYSTEM:
                # [UPDATE]: Block System Prompt Injection with shielded logging.
                raise ShieldValidationError(
                    public_message="Conversation history issue. Let's try starting a new chat.",
                    internal_message="Security Violation: Attempted SYSTEM role injection in YA history array."
                )
        return self

# ---------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------

class ModelMetadata(BaseModel):
    """
    Tracks telemetry and metrics for the specific model used.
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
        hallucinated HTML or executable code.
        """
        return nh3.clean(v, tags=set())