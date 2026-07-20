"""
src/legal/models.py

Defines the SQLAlchemy models for the Legal & Terms of Service ecosystem.
Synchronized with the central `db.Base` declarative base using classic syntax.
"""

import uuid
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID

# Import your central Base (assuming it lives here based on your snippet)
from db import Base

class DocumentSignature(Base):
    """
    The absolute source of truth for the legal audit trail.
    Tracks cryptographically sealed Terms of Service agreements.
    """
    __tablename__ = "document_signatures"

    # Unique ID using native Postgres UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # User Details
    client_name = Column(String(255), nullable=False)
    client_email = Column(String(255), index=True, nullable=False)
    
    # Audit Trail Data
    ip_address = Column(String(45), nullable=False) # 45 chars supports IPv6 max length
    
    # The Cryptographic Lock (SHA-256 is exactly 64 characters)
    document_hash = Column(String(64), unique=True, index=True, nullable=False)
    
    # The link to the actual PDF living in Supabase Storage
    storage_path = Column(String(512), nullable=False)
    
    # The exact UTC moment the document was cryptographically sealed
    signed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<DocumentSignature(email='{self.client_email}', signed_at='{self.signed_at}')>"