import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from backend.models.user import Base as UserBase
from backend.models.video import Base as VideoBase

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost/video_gallery')

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,  # Use NullPool for better connection management
    echo=os.getenv('DEBUG', 'False').lower() == 'true'  # Log SQL in debug mode
)

# Create session factory
SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Thread-safe session
Session = scoped_session(SessionFactory)

def init_db():
    """Initialize database tables"""
    # Import all models to ensure they're registered
    from backend.models.user import User
    from backend.models.video import Video
    
    # Create all tables
    UserBase.metadata.create_all(engine)
    VideoBase.metadata.create_all(engine)
    
    print("Database tables created successfully!")

def drop_db():
    """Drop all database tables (use with caution!)"""
    UserBase.metadata.drop_all(engine)
    VideoBase.metadata.drop_all(engine)
    print("Database tables dropped!")

@contextmanager
def get_db_session():
    """
    Context manager for database sessions.
    Ensures proper cleanup and error handling.
    
    Usage:
        with get_db_session() as session:
            user = session.query(User).first()
    """
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_db():
    """
    Dependency function for FastAPI/Flask routes.
    
    Usage in Flask:
        @app.route('/users')
        def get_users():
            db = next(get_db())
            users = db.query(User).all()
            db.close()
            return users
    """
    session = Session()
    try:
        yield session
    finally:
        session.close()

# Utility functions for common queries
def get_user_by_email(email):
    """Get user by email address"""
    with get_db_session() as session:
        from backend.models.user import User
        return session.query(User).filter(User.email == email).first()

def get_user_by_id(user_id):
    """Get user by ID"""
    with get_db_session() as session:
        from backend.models.user import User
        return session.query(User).filter(User.id == user_id).first()

def get_video_by_id(video_id):
    """Get video by ID"""
    with get_db_session() as session:
        from backend.models.video import Video
        return session.query(Video).filter(Video.id == video_id).first()

def get_user_videos(user_id, limit=None):
    """Get all videos for a user"""
    with get_db_session() as session:
        from backend.models.video import Video
        query = session.query(Video).filter(Video.user_id == user_id)
        if limit:
            query = query.limit(limit)
        return query.all()"