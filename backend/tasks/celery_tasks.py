from celery import Celery, Task
import os
from dotenv import load_dotenv
from datetime import datetime
import logging
import time
from backend.utils.database import get_db_session
from backend.models.video import Video
from backend.services.aws_service import aws_service

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    enable_utc=True,
    task_routes={
        'tasks.process_video': {'queue': 'video_processing'},
        'tasks.analyze_video': {'queue': 'ai_analysis'},
    },
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3000,  # 50 minutes soft limit
)

class CallbackTask(Task):
    """Task that sends real-time updates via WebSocket"""
    def on_success(self, retval, task_id, args, kwargs):
        """Called on successful completion"""
        logger.info(f"Task {task_id} completed successfully")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called on task failure"""
        logger.error(f"Task {task_id} failed: {exc}")

def emit_status_update(video_id, status, message=None, progress=None):
    """Emit status update via WebSocket"""
    try:
        # Import here to avoid circular imports
        from app import socketio
        
        # Get video to find user_id
        with get_db_session() as db:
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                data = {
                    'video_id': str(video_id),
                    'status': status,
                    'message': message,
                    'progress': progress
                }
                
                socketio.emit('processing_update', data, room=f'user_{video.user_id}')
                logger.info(f"Emitted status update for video {video_id}: {status}")
    except Exception as e:
        logger.warning(f"Could not emit status update: {str(e)}")

@celery_app.task(bind=True, base=CallbackTask, name='tasks.process_video')
def process_video_task(self, video_id):
    """
    Process uploaded video - extract metadata and prepare for AI analysis
    
    Args:
        video_id: UUID of the video to process
    """
    logger.info(f"Starting video processing for: {video_id}")
    
    try:
        # Update status to processing
        with get_db_session() as db:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise Exception(f"Video {video_id} not found")
            
            video.status = 'processing'
            video.processing_started_at = datetime.utcnow()
            db.commit()
        
        emit_status_update(video_id, 'processing', 'Starting video analysis...', 10)
        
        # Step 1: Start AWS Rekognition label detection
        logger.info(f"Starting Rekognition analysis for video {video_id}")
        label_job = aws_service.analyze_video_labels(video.s3_key)
        emit_status_update(video_id, 'processing', 'Analyzing video content...', 25)
        
        # Step 2: Start face detection
        face_job = aws_service.detect_faces_in_video(video.s3_key)
        emit_status_update(video_id, 'processing', 'Detecting faces...', 35)
        
        # Step 3: Start content moderation
        moderation_job = aws_service.detect_content_moderation(video.s3_key)
        emit_status_update(video_id, 'processing', 'Checking content safety...', 45)
        
        # Step 4: Start transcription
        job_name = f"transcribe_{video_id}_{int(time.time())}"
        transcription_job = aws_service.start_transcription(video.s3_key, job_name)
        emit_status_update(video_id, 'processing', 'Transcribing audio...', 55)
        
        # Store job IDs for polling
        with get_db_session() as db:
            video = db.query(Video).filter(Video.id == video_id).first()
            
            # Store job information in detected_objects temporarily
            video.detected_objects = {
                'rekognition_jobs': {
                    'label_detection': label_job,
                    'face_detection': face_job,
                    'content_moderation': moderation_job
                },
                'transcribe_job': transcription_job
            }
            db.commit()
        
        # Schedule the analysis task to check results
        analyze_video_task.apply_async(
            args=[video_id],
            countdown=30  # Check after 30 seconds
        )
        
        emit_status_update(video_id, 'processing', 'AI analysis in progress...', 65)
        
        return {
            'video_id': video_id,
            'status': 'processing',
            'jobs_started': True
        }
        
    except Exception as e:
        logger.error(f"Error processing video {video_id}: {str(e)}")
        
        # Update video status to failed
        with get_db_session() as db:
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.status = 'failed'
                video.error_message = str(e)
                video.processing_completed_at = datetime.utcnow()
                db.commit()
        
        emit_status_update(video_id, 'failed', f'Processing failed: {str(e)}')
        
        raise

@celery_app.task(bind=True, name='tasks.analyze_video', max_retries=10)
def analyze_video_task(self, video_id):
    """
    Check AWS job results and complete video analysis
    """
    try:
        with get_db_session() as db:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise Exception(f"Video {video_id} not found")
            
            jobs = video.detected_objects or {}
            rekognition_jobs = jobs.get('rekognition_jobs', {})
            transcribe_job = jobs.get('transcribe_job', {})
        
        all_complete = True
        results = {}
        
        # Check Rekognition label detection
        if 'label_detection' in rekognition_jobs:
            label_results = aws_service.get_label_detection_results(
                rekognition_jobs['label_detection']['job_id']
            )
            if label_results['status'] == 'completed':
                results['labels'] = label_results['labels']
                results['video_metadata'] = label_results.get('video_metadata', {})
            else:
                all_complete = False
        
        # Check face detection
        if 'face_detection' in rekognition_jobs:
            try:
                face_results = aws_service.rekognition_client.get_face_detection(
                    JobId=rekognition_jobs['face_detection']['job_id']
                )
                if face_results['JobStatus'] == 'SUCCEEDED':
                    results['faces'] = face_results.get('Faces', [])
                elif face_results['JobStatus'] != 'IN_PROGRESS':
                    logger.warning(f"Face detection failed for video {video_id}")
                else:
                    all_complete = False
            except Exception as e:
                logger.error(f"Error getting face detection results: {str(e)}")
        
        # Check content moderation
        if 'content_moderation' in rekognition_jobs:
            try:
                moderation_results = aws_service.rekognition_client.get_content_moderation(
                    JobId=rekognition_jobs['content_moderation']['job_id']
                )
                if moderation_results['JobStatus'] == 'SUCCEEDED':
                    results['moderation'] = moderation_results.get('ModerationLabels', [])
                elif moderation_results['JobStatus'] != 'IN_PROGRESS':
                    logger.warning(f"Content moderation failed for video {video_id}")
                else:
                    all_complete = False
            except Exception as e:
                logger.error(f"Error getting moderation results: {str(e)}")
        
        # Check transcription
        if transcribe_job:
            transcription_results = aws_service.get_transcription_results(
                transcribe_job['job_name']
            )
            if transcription_results['status'] == 'completed':
                results['transcript'] = transcription_results['transcript']
                
                # Analyze transcript with Comprehend
                if results['transcript']:
                    emit_status_update(video_id, 'processing', 'Analyzing transcript...', 85)
                    
                    # Sentiment analysis
                    sentiment = aws_service.analyze_text_sentiment(results['transcript'])
                    results['sentiment'] = sentiment
                    
                    # Key phrases
                    key_phrases = aws_service.extract_key_phrases(results['transcript'])
                    results['key_phrases'] = key_phrases
                    
                    # Named entities
                    entities = aws_service.detect_entities(results['transcript'])
                    results['entities'] = entities
            else:
                all_complete = False
        
        # If all jobs are complete, update the video
        if all_complete:
            emit_status_update(video_id, 'processing', 'Finalizing analysis...', 95)
            
            with get_db_session() as db:
                video = db.query(Video).filter(Video.id == video_id).first()
                
                # Update video with results
                video.detected_objects = results.get('labels', {})
                video.detected_faces = results.get('faces', [])
                video.moderation_labels = results.get('moderation', [])
                video.transcript = results.get('transcript', '')
                video.sentiment_analysis = results.get('sentiment', {})
                video.key_phrases = results.get('key_phrases', [])
                video.entities = results.get('entities', [])
                
                # Extract categories and additional tags
                categories = []
                additional_tags = []
                
                # Add high-confidence labels as tags
                for label_name, label_data in results.get('labels', {}).items():
                    if label_data['confidence'] > 80:
                        additional_tags.append(label_name.lower())
                
                # Add entity types as categories
                for entity in results.get('entities', []):
                    if entity['type'] in ['PERSON', 'LOCATION', 'ORGANIZATION']:
                        categories.append(entity['type'].lower())
                
                # Update tags and categories
                video.tags = list(set(video.tags + additional_tags))[:20]  # Limit to 20 tags
                video.categories = list(set(categories))
                
                # Mark as completed
                video.status = 'completed'
                video.processing_completed_at = datetime.utcnow()
                video.error_message = None
                
                db.commit()
            
            emit_status_update(video_id, 'completed', 'Analysis complete!', 100)
            
            logger.info(f"Video {video_id} processing completed successfully")
            
            return {
                'video_id': video_id,
                'status': 'completed',
                'results': results
            }
        
        else:
            # Jobs still running, retry after delay
            emit_status_update(video_id, 'processing', 'AI analysis in progress...', 75)
            
            raise self.retry(countdown=30, max_retries=10)
            
    except Exception as e:
        if 'retry' in str(e).lower():
            raise  # Re-raise retry exceptions
        
        logger.error(f"Error analyzing video {video_id}: {str(e)}")
        
        # Update video status to failed
        with get_db_session() as db:
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.status = 'failed'
                video.error_message = f"Analysis failed: {str(e)}"
                video.processing_completed_at = datetime.utcnow()
                db.commit()
        
        emit_status_update(video_id, 'failed', f'Analysis failed: {str(e)}')
        
        raise

@celery_app.task(name='tasks.cleanup_old_jobs')
def cleanup_old_jobs():
    """
    Periodic task to clean up old processing jobs
    """
    try:
        # Find videos stuck in processing for more than 2 hours
        from datetime import timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=2)
        
        with get_db_session() as db:
            stuck_videos = db.query(Video).filter(
                Video.status == 'processing',
                Video.processing_started_at < cutoff_time
            ).all()
            
            for video in stuck_videos:
                video.status = 'failed'
                video.error_message = 'Processing timeout - please try uploading again'
                video.processing_completed_at = datetime.utcnow()
                
                emit_status_update(video.id, 'failed', 'Processing timeout')
            
            db.commit()
            
            if stuck_videos:
                logger.info(f"Cleaned up {len(stuck_videos)} stuck videos")
    
    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")

# Celery beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'cleanup-old-jobs': {
        'task': 'tasks.cleanup_old_jobs',
        'schedule': 300.0,  # Run every 5 minutes
    },
}