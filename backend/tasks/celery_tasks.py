from celery import Celery
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Celery
celery_app = Celery(
    'video_gallery',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True
)

@celery_app.task
def process_video_task(video_id):
    """Process uploaded video"""
    # TODO: Implement video processing
    print(f"Processing video: {video_id}")
    return {'status': 'completed', 'video_id': video_id}