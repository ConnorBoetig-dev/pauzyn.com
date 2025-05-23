import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration class"""
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://localhost/video_gallery')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # File Upload
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 500)) * 1024 * 1024  # MB to bytes
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'temp')
    ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_VIDEO_EXTENSIONS', 'mp4,avi,mov,mkv,webm').split(','))
    
    # AWS
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
    
    # Celery
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = 'UTC'
    CELERY_ENABLE_UTC = True
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    # Video Processing
    VIDEO_PROCESSING_TIMEOUT = 3600  # 1 hour
    THUMBNAIL_SIZE = (320, 180)
    
    # AI Services
    REKOGNITION_MIN_CONFIDENCE = 70
    TRANSCRIBE_LANGUAGE_CODE = 'en-US'
    COMPREHEND_LANGUAGE_CODE = 'en'
    
    # Vector Search
    VECTOR_DIMENSION = 1536  # Dimension for embeddings
    SIMILARITY_THRESHOLD = 0.7  # Minimum similarity score for search results

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    ENV = 'development'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    ENV = 'production'
    
    # Override for production
    SESSION_COOKIE_SECURE = True
    
    # Use environment variables for sensitive data
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable must be set in production")

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    
    # Use in-memory SQLite for tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])