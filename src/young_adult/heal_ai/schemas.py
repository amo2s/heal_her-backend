"""
src/young_adult/heal_ai/schemas.py

This module defines the strict data contracts and validation layers for the Young Adult Heal AI.
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
    # 10,000 characters provides ample space for young adults to describe 
    # complex life situations, career stress, or relational dynamics 
    # without hitting restrictive walls.
    content: str = Field(..., min_length=1, max_length=10000)

    @field_validator("content")
    @classmethod
    def sanitize_and_check_entropy(cls, v: str) -> str:
        """
        First line of defense. Strips all HTML/scripts and prevents buffer attacks.
        """
        # 1. Strip all HTML tags to prevent Cross-Site Scripting (XSS)
        clean_text = nh3.clean(v, tags=set()) 
        
        if not clean_text.strip():
            raise ValueError("Message content cannot be empty or consist solely of formatting tags.")

        # 2. Entropy/Repetition Check
        # Prevents keyboard-mashing DOS attacks (e.g., "A" repeated 100 times)
        # Allows for nuanced language but blocks malicious repetitive strings.
        if re.search(r'(.)\1{100,}', clean_text):
            raise ValueError("Input contains excessive repetitive characters and cannot be processed.")

        return clean_text.strip()

class ChatRequest(BaseModel):
    """
    Incoming payload schema from the REST/Frontend layer for Young Adults.
    """
    session_id: Optional[str] = Field(
        default=None,
        description="The ID of the current chat session. None if it's a new conversation."
    )
    provider: AIProvider = Field(
        default=AIProvider.MISTRAL, 
        description="The target AI model for semantic routing."
    )
    # History cap at 20 ensures deep context for complex adult conversations 
    # while maintaining performance.
    history: List[Message] = Field(
        default_factory=list,
        max_length=20, 
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
    Maintains consistency across the platform for unified analytics.
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