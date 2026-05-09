"""
src/teens/heal_ai/models.py

Defines the SQLAlchemy models for the Teens Heal AI ecosystem.
Synchronized with the central `User` identity table using classic declarative syntax.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Index, func
from sqlalchemy.orm import relationship

# Import your central Base
from db import Base

class TeensChatSession(Base):
    """
    The parent thread for a conversation. Tied directly to the central User table.
    Isolated for the Teens demographic.
    """
    __tablename__ = "teens_chat_sessions"

    # Using String(36) to comfortably store UUIDv7 strings
    id = Column(String(36), primary_key=True, index=True, nullable=False)
    
    # Strict Relational Binding to your central users table
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    
    # AI-generated summary for the sidebar
    title = Column(String(100), nullable=True)
    
    # Tracks the user's selected session intent (e.g., "Venting", "Advice", "Learning", "Crisis")
    intent = Column(String(50), nullable=True)
    
    # Soft deletion for user control + safety audits
    is_deleted = Column(Boolean, default=False, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships (Note: backref is strictly isolated to teens_chat_sessions to prevent collisions)
    user = relationship("User", backref="teens_chat_sessions")
    messages = relationship(
        "TeensChatMessage", 
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="TeensChatMessage.created_at"
    )

    # Composite index for lightning-fast sidebar queries
    __table_args__ = (
        Index("idx_teens_user_active_sessions", "user_id", "is_deleted"),
    )


class TeensChatMessage(Base):
    """
    Individual encrypted message logs within a teens session.
    """
    __tablename__ = "teens_chat_messages"

    id = Column(String(36), primary_key=True, index=True, nullable=False)
    
    # Binds to the TeensChatSession. If session is deleted, messages cascade delete.
    session_id = Column(String(36), ForeignKey("teens_chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    
    # 'user', 'assistant', 'system'
    role = Column(String(10), nullable=False) 
    
    # Application-Layer Encrypted Payload
    encrypted_content = Column(Text, nullable=False)
    
    # Telemetry and billing metadata
    provider_used = Column(String(50), nullable=True)
    tokens_consumed = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship back to the session
    session = relationship("TeensChatSession", back_populates="messages")