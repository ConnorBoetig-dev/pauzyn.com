from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from pgvector.sqlalchemy import Vector
import uuid

Base = declarative_base()

class Video(Base):
    """Video model with metadata and AI analysis results"""
    __tablename__ = 'videos'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Basic video information
    title = Column(String(255), nullable=False)
    description = Column(Text)
    filename = Column(String(255), nullable=False)
    s3_key = Column(String(500), nullable=False, unique=True)
    s3_url = Column(String(1000))
    thumbnail_url = Column(String(1000))
    
    # Video metadata
    duration = Column(Float)  # Duration in seconds
    file_size = Column(Integer)  # Size in bytes
    format = Column(String(50))
    resolution = Column(String(20))
    fps = Column(Float)
    
    # Processing status
    status = Column(String(50), default='pending')  # pending, processing, completed, failed
    processing_started_at = Column(DateTime)
    processing_completed_at = Column(DateTime)
    error_message = Column(Text)
    
    # AI Analysis Results
    # Visual analysis (AWS Rekognition)
    detected_objects = Column(JSON)  # List of objects with confidence scores
    detected_scenes = Column(JSON)   # Scene descriptions
    detected_faces = Column(JSON)    # Face analysis results
    detected_emotions = Column(JSON) # Emotional analysis
    moderation_labels = Column(JSON) # Content moderation results
    
    # Audio analysis (AWS Transcribe + Comprehend)
    transcript = Column(Text)        # Full transcript
    detected_languages = Column(JSON) # Language detection results
    key_phrases = Column(JSON)       # Key phrases from transcript
    sentiment_analysis = Column(JSON) # Sentiment scores
    entities = Column(JSON)          # Named entities from transcript
    
    # Search and categorization
    tags = Column(ARRAY(String))     # User and AI generated tags
    categories = Column(ARRAY(String)) # Video categories
    
    # Vector embeddings for similarity search
    visual_embedding = Column(Vector(1536))  # Visual features vector
    audio_embedding = Column(Vector(1536))   # Audio features vector
    combined_embedding = Column(Vector(1536)) # Combined features vector
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship('User', back_populates='videos')
    
    def to_dict(self):
        """Convert video object to dictionary"""
        return {
            'id': str(self.id),
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'filename': self.filename,
            's3_url': self.s3_url,
            'thumbnail_url': self.thumbnail_url,
            'duration': self.duration,
            'file_size': self.file_size,
            'format': self.format,
            'resolution': self.resolution,
            'status': self.status,
            'tags': self.tags,
            'categories': self.categories,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processing_completed_at': self.processing_completed_at.isoformat() if self.processing_completed_at else None
        }
    
    def to_search_result(self):
        """Convert to search result format"""
        return {
            'id': str(self.id),
            'title': self.title,
            'description': self.description,
            'thumbnail_url': self.thumbnail_url,
            'duration': self.duration,
            'tags': self.tags,
            'relevance_score': None  # Will be set by search function
        }
    
    def __repr__(self):
        return f'<Video {self.title}>'"