import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from db import Base # Using your unified database Base

# =====================================================================
# THE STRICT TYPING REGISTRY
# =====================================================================
class StaffRole(str, PyEnum):
    """
    Extremist RBAC (Role-Based Access Control) Definitions.
    PENDING_STAFF is a dead-end role with absolutely zero privileges.
    """
    PENDING_STAFF = "PENDING_STAFF"  # Default trap state
    SUPER_ADMIN = "SUPER_ADMIN"      # God-mode (You)
    ADMIN = "ADMIN"                  # High-level management
    MODERATOR = "MODERATOR"          # Can approve content/users, cannot delete
    TEACHER = "TEACHER"              # Can upload educational content
    CONTENT_CREATOR = "CONTENT_CREATOR" # Strictly restricted to content generation

class StaffStatus(str, PyEnum):
    """
    The State-Machine Gate. 
    Even if a password is valid, if status != ACTIVE, the JWT generator crashes the request.
    """
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


# =====================================================================
# THE MANAGEMENT FORTRESS TABLE
# =====================================================================
class Staff(Base):
    """
    Physically isolated from the `users` (Kids) table. 
    A breach in the Kids API cannot elevate privileges here because 
    this table does not exist in that domain's context.
    """
    __tablename__ = "staff_users"

    # 1. Core Identity
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    
    # 2. Cryptography
    # We allocate 255 chars to comfortably fit Argon2id hashes
    hashed_password = Column(String(255), nullable=False)

    # 3. The State Machine & RBAC Gate
    # native_enum=True forces PostgreSQL to enforce these strings at the hardware level
    role = Column(
        Enum(StaffRole, name="staff_role_enum", native_enum=True), 
        default=StaffRole.PENDING_STAFF, 
        nullable=False
    )
    status = Column(
        Enum(StaffStatus, name="staff_status_enum", native_enum=True), 
        default=StaffStatus.PENDING, 
        nullable=False
    )

    # 4. Zero-Trust Audit Trail (Hardware/Network tracking)
    signup_ip = Column(String(45), nullable=True) # 45 characters supports full IPv6 addresses
    signup_user_agent = Column(Text, nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # 5. The "Paper Trail" of Authority (Self-Referential)
    # If a rogue teacher is approved, this tells you exactly WHICH Admin approved them.
    approved_by_id = Column(String(36), ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # 6. Temporal Tracking
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # -----------------------------------------------------------------
    # RELATIONSHIPS
    # -----------------------------------------------------------------
    # This creates a link to see the Staff object of the person who approved this user.
    # remote_side=[id] handles the self-referencing foreign key cleanly.
    approved_by = relationship("Staff", remote_side=[id], backref="approved_users")

    def __repr__(self):
        return f"<Staff(email='{self.email}', role='{self.role}', status='{self.status}')>"