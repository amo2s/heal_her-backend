"""
src/kids/ai_buddy/models.py

Defines the SQLAlchemy models for the Kids AI Buddy ecosystem.
Synchronized with the central `User` identity table using classic declarative syntax.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Index, func
from sqlalchemy.orm import relationship

# Import your central Base
from db import Base

class ChatSession(Base):
    """
    The parent thread for a conversation. Tied directly to the central User table.
    """
    __tablename__ = "kids_chat_sessions"

    # Using String(36) to comfortably store UUIDv7 strings
    id = Column(String(36), primary_key=True, index=True, nullable=False)
    
    # Strict Relational Binding to your central users table
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    
    # AI-generated summary for the sidebar
    title = Column(String(100), nullable=True)
    
    # Soft deletion for user control + safety audits
    is_deleted = Column(Boolean, default=False, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="kids_chat_sessions")
    messages = relationship(
        "ChatMessage", 
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at"
    )

    # Composite index for lightning-fast sidebar queries
    __table_args__ = (
        Index("idx_user_active_sessions", "user_id", "is_deleted"),
    )


class ChatMessage(Base):
    """
    Individual encrypted message logs within a session.
    """
    __tablename__ = "kids_chat_messages"

    id = Column(String(36), primary_key=True, index=True, nullable=False)
    
    # Binds to the ChatSession. If session is deleted, messages cascade delete.
    session_id = Column(String(36), ForeignKey("kids_chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    
    role = Column(String(10), nullable=False) # 'user', 'assistant', 'system'
    
    # Application-Layer Encrypted Payload
    encrypted_content = Column(Text, nullable=False)
    
    # Telemetry and billing metadata
    provider_used = Column(String(50), nullable=True)
    tokens_consumed = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship back to the session
    session = relationship("ChatSession", back_populates="messages")