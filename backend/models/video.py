# models/video.py
from datetime import datetime
import uuid

from sqlalchemy import (
    Column, Integer, String, DateTime, Text, JSON,
    ForeignKey, Float
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from pgvector.sqlalchemy import Vector
from backend.models import Base
          


class Video(Base):
    """Video model with metadata and AI analysis results."""
    __tablename__ = "videos"

    # Primary / foreign keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Basic video info
    title = Column(String(255), nullable=False)
    description = Column(Text)
    filename = Column(String(255), nullable=False)
    s3_key = Column(String(500), nullable=False, unique=True)
    s3_url = Column(String(1000))
    thumbnail_url = Column(String(1000))

    # Raw metadata
    duration = Column(Float)          # seconds
    file_size = Column(Integer)       # bytes
    format = Column(String(50))
    resolution = Column(String(20))
    fps = Column(Float)

    # Processing status
    status = Column(String(50), default="pending")   # pending | processing | completed | failed
    processing_started_at = Column(DateTime)
    processing_completed_at = Column(DateTime)
    error_message = Column(Text)

    # AI analysis results
    detected_objects   = Column(JSON)
    detected_scenes    = Column(JSON)
    detected_faces     = Column(JSON)
    detected_emotions  = Column(JSON)
    moderation_labels  = Column(JSON)

    transcript         = Column(Text)
    detected_languages = Column(JSON)
    key_phrases        = Column(JSON)
    sentiment_analysis = Column(JSON)
    entities           = Column(JSON)

    # Search helpers
    tags       = Column(ARRAY(String))
    categories = Column(ARRAY(String))

    # Vector embeddings
  #  visual_embedding   = Column(Vector(1536))
   # audio_embedding    = Column(Vector(1536))
    #combined_embedding = Column(Vector(1536))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship back to User
    user = relationship("User", back_populates="videos")

    # Helper serializers ----------------------------------------------------
    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "filename": self.filename,
            "s3_url": self.s3_url,
            "thumbnail_url": self.thumbnail_url,
            "duration": self.duration,
            "file_size": self.file_size,
            "format": self.format,
            "resolution": self.resolution,
            "status": self.status,
            "tags": self.tags,
            "categories": self.categories,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processing_completed_at": (
                self.processing_completed_at.isoformat()
                if self.processing_completed_at
                else None
            ),
        }

    def to_search_result(self):
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "thumbnail_url": self.thumbnail_url,
            "duration": self.duration,
            "tags": self.tags,
            "relevance_score": None,  # set by search layer
        }

    def __repr__(self):
        return f"<Video {self.title}>"
