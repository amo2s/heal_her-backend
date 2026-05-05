import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, 
    String, 
    Text, 
    Integer, 
    DateTime, 
    ForeignKey, 
    CheckConstraint, 
    UniqueConstraint, 
    Index
)
from sqlalchemy.orm import declarative_mixin, declared_attr, relationship

# Adjust this import to point to your actual SQLAlchemy Base instance
from db import Base 

# =====================================================================
# 1. THE MIXIN BLUEPRINT (DRY Architecture)
# =====================================================================
@declarative_mixin
class VideoContentMixin:
    """
    The master blueprint for all Video tables (Kids, Teens, Adults).
    Alembic reads this to generate identical physical columns for isolated tables.
    """
    @declared_attr
    def id(cls):
        # Using string UUIDs for compatibility with GraphQL and Next.js mapping
        return Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    @declared_attr
    def title(cls):
        return Column(String(255), nullable=False, index=True)

    @declared_attr
    def topic(cls):
        return Column(String(100), nullable=False, index=True)

    @declared_attr
    def duration(cls):
        # e.g., "5:30"
        return Column(String(10), nullable=False)

    @declared_attr
    def thumbnail_url(cls):
        return Column(String(500), nullable=True)

    @declared_attr
    def video_url(cls):
        return Column(String(500), nullable=False)

    @declared_attr
    def transcript(cls):
        # Text type allows for long paragraphs, ideal for text-to-speech and Low Data Mode
        return Column(Text, nullable=True)

    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @declared_attr
    def updated_at(cls):
        return Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# =====================================================================
# 2. THE PHYSICAL VIDEO TABLE (Kids Isolated)
# =====================================================================
class KidVideo(VideoContentMixin, Base):
    """
    Physical Table: kid_videos
    Strictly walled off from other age groups.
    """
    __tablename__ = "kid_videos"

    # Bidirectional relationship for clean querying (Optional but recommended)
    progress_records = relationship(
        "KidVideoProgress", 
        back_populates="video", 
        cascade="all, delete-orphan"
    )


# =====================================================================
# 3. THE ISOLATED PROGRESS TABLE
# =====================================================================
class KidVideoProgress(Base):
    """
    Physical Table: kid_video_progress
    Tracks exactly how far a specific kid has watched a specific kid video.
    """
    __tablename__ = "kid_video_progress"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Links to the central users table
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Links strictly to the kid_videos table
    video_id = Column(String(36), ForeignKey("kid_videos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    watched_percentage = Column(Integer, default=0, nullable=False)
    last_watched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Bidirectional relationship back to the video
    video = relationship("KidVideo", back_populates="progress_records")

    # The Smart Constraints
    __table_args__ = (
        # 1. Ensure a user can only have ONE progress record per video
        UniqueConstraint('user_id', 'video_id', name='uix_kid_user_video_progress'),
        
        # 2. Database-level firewall: Progress cannot mathematically exceed 100 or drop below 0
        CheckConstraint('watched_percentage >= 0 AND watched_percentage <= 100', name='chk_kid_watched_percentage_range'),
        
        # 3. Compound index to make lookup insanely fast when loading the dashboard
        Index('idx_kid_user_video', 'user_id', 'video_id'),
    )