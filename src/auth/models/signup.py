from sqlalchemy import Column, String, DateTime, Integer, Boolean, func
from sqlalchemy.orm import validates

# Import the central Base and settings to link everything together
from db import Base
from core.config import settings

class User(Base):
    """
    The Central User Identity Table.
    Updated with the 'role' column to drive the HEAL Her Guardrail system.
    """
    __tablename__ = "users"

    # Primary Key using UUIDv7 (String format for maximum compatibility)
    id = Column(String, primary_key=True, index=True, nullable=False)
    
    # Core Identity
    full_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    
    # The 'age' column: The mechanical engine for our dashboard segmentation
    # Used to route users to Kids (<=12), Teens (13-17), or Young Adult (18+)
    age = Column(Integer, nullable=False)

    # --- THE ROLE COLUMN: The Security Key ---
    # Stores: 'kid', 'teen', or 'young-adult'
    role = Column(String(20), nullable=False, index=True)
    
    # Security - Argon2id hashes
    password_hash = Column(String(255), nullable=False)

    # --- SECURITY FLAGS ---
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Status & Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # --- VALIDATION (Optional but Recommended) ---
    @validates('role')
    def validate_role(self, key, value):
        allowed_roles = ["kid", "teen", "young-adult", "admin"]
        if value not in allowed_roles:
            raise ValueError(f"Invalid role: {value}. Must be one of {allowed_roles}")
        return value

    def __repr__(self):
        return f"<User(email={self.email}, role={self.role}, age={self.age}, id={self.id})>"