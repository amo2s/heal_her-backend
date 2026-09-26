"""
src/terms/models.py

Defines the SQLAlchemy models for the Legal & Terms of Service ecosystem.
Synchronized with the central `db.Base` declarative base using classic syntax.
"""

import uuid
from sqlalchemy import Column, String, Integer, DateTime, Boolean, func, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID

from db import Base


class TOSAuditLedger(Base):
    """
    The absolute source of truth for the legal audit trail.
    Tracks cryptographically sealed Terms of Service agreements.
    Includes mandatory dual-track execution for parental consent.
    """
    __tablename__ = "tos_audit_ledger"

    # Unique ID using native Postgres UUID
    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Primary Signer Details (Adult or Guardian)
    client_name = Column(String(255), nullable=False)
    client_email = Column(String(255), index=True, nullable=False)
    
    # Parental Consent Dual-Track Fields
    is_parental_consent = Column(Boolean, nullable=False, default=False)
    minor_name = Column(String(255), nullable=True)
    minor_age = Column(Integer, nullable=True)
    
    # Audit Trail Data
    ip_address = Column(String(45), nullable=False)
    
    # The Cryptographic Lock (SHA-512 is 128 characters)
    sha512_hash = Column(String(128), unique=True, index=True, nullable=False)
    
    # The link to the actual PDF living in Supabase Storage
    storage_path = Column(String(512), nullable=False)
    
    # The exact UTC moment the document was cryptographically sealed
    execution_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Database-level constraint to strictly enforce consent logic
    __table_args__ = (
        CheckConstraint(
            "(is_parental_consent = false AND minor_name IS NULL AND minor_age IS NULL) OR "
            "(is_parental_consent = true AND minor_name IS NOT NULL AND minor_age <= 17)",
            name="chk_parental_consent"
        ),
    )

    def __repr__(self) -> str:
        return f"<TOSAuditLedger(email='{self.client_email}', executed_at='{self.execution_timestamp}')>"