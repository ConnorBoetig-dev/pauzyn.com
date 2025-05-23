from flask import Blueprint, request, jsonify, session
from werkzeug.utils import secure_filename
from backend.routes.auth import login_required
from backend.models.video import Video
from backend.utils.database import get_db_session
from backend.services.aws_service import aws_service
from backend.tasks.celery_tasks import process_video_task
import os
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

upload_bp = Blueprint('upload', __name__)

# Allowed video extensions
ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_VIDEO_EXTENSIONS', 'mp4,avi,mov,mkv,webm').split(','))

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_info(file):
    """Extract basic file information"""
    filename = secure_filename(file.filename)
    extension = filename.rsplit('.', 1)[1].lower()
    file_size = file.content_length or 0
    
    return {
        'filename': filename,
        'extension': extension,
        'file_size': file_size
    }

@upload_bp.route('/upload', methods=['POST'])
@login_required
def upload_video():
    """Handle video file upload"""
    try:
        # Check if file is present
        if 'video' not in request.files:
            return jsonify({'error': 'No video file provided'}), 400
        
        file = request.files['video']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'error': f'Invalid file type. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # Get video metadata from request
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        tags = request.form.getlist('tags[]')  # Array of tags
        
        if not title:
            title = file.filename.rsplit('.', 1)[0]  # Use filename as title if not provided
        
        # Get file information
        file_info = get_file_info(file)
        
        # Generate unique S3 key
        video_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        s3_key = f"videos/{session['user_id']}/{timestamp}_{video_id}.{file_info['extension']}"
        
        # Save file temporarily
        temp_dir = os.path.join(os.getcwd(), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{video_id}.{file_info['extension']}")
        file.save(temp_path)
        
        try:
            # Upload to S3
            logger.info(f"Uploading video to S3: {s3_key}")
            s3_url = aws_service.upload_video_to_s3(temp_path, s3_key)
            
            # Create database entry
            with get_db_session() as db:
                new_video = Video(
                    id=uuid.UUID(video_id),
                    user_id=session['user_id'],
                    title=title,
                    description=description,
                    filename=file_info['filename'],
                    s3_key=s3_key,
                    s3_url=s3_url,
                    file_size=file_info['file_size'],
                    format=file_info['extension'],
                    status='uploaded',
                    tags=tags if tags else []
                )
                
                db.add(new_video)
                db.commit()
                
                # Trigger background processing
                process_video_task.delay(str(new_video.id))
                
                # Clean up temp file
                os.remove(temp_path)
                
                # Emit real-time update
                from app import socketio
                socketio.emit('upload_complete', {
                    'video_id': str(new_video.id),
                    'status': 'uploaded',
                    'message': 'Video uploaded successfully. Processing started.'
                }, room=f'user_{session["user_id"]}')
                
                return jsonify({
                    'message': 'Video uploaded successfully',
                    'video': new_video.to_dict()
                }), 201
                
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e
            
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@upload_bp.route('/', methods=['GET'])
@login_required
def get_user_videos():
    """Get all videos for the current user"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        with get_db_session() as db:
            # Query videos with pagination
            videos_query = db.query(Video).filter(
                Video.user_id == session['user_id']
            ).order_by(Video.created_at.desc())
            
            # Get total count
            total = videos_query.count()
            
            # Get paginated results
            videos = videos_query.offset((page - 1) * per_page).limit(per_page).all()
            
            return jsonify({
                'videos': [video.to_dict() for video in videos],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            }), 200
            
    except Exception as e:
        logger.error(f"Failed to get videos: {str(e)}")
        return jsonify({'error': 'Failed to retrieve videos'}), 500

@upload_bp.route('/<video_id>', methods=['GET'])
@login_required
def get_video(video_id):
    """Get specific video details"""
    try:
        with get_db_session() as db:
            video = db.query(Video).filter(
                Video.id == video_id,
                Video.user_id == session['user_id']
            ).first()
            
            if not video:
                return jsonify({'error': 'Video not found'}), 404
            
            # Generate presigned URL for secure access
            presigned_url = aws_service.generate_presigned_url(video.s3_key)
            video_dict = video.to_dict()
            video_dict['presigned_url'] = presigned_url
            
            return jsonify({'video': video_dict}), 200
            
    except Exception as e:
        logger.error(f"Failed to get video: {str(e)}")
        return jsonify({'error': 'Failed to retrieve video'}), 500

@upload_bp.route('/<video_id>', methods=['DELETE'])
@login_required
def delete_video(video_id):
    """Delete a video"""
    try:
        with get_db_session() as db:
            video = db.query(Video).filter(
                Video.id == video_id,
                Video.user_id == session['user_id']
            ).first()
            
            if not video:
                return jsonify({'error': 'Video not found'}), 404
            
            # Delete from S3
            if aws_service.delete_video_from_s3(video.s3_key):
                # Delete from database
                db.delete(video)
                db.commit()
                
                return jsonify({'message': 'Video deleted successfully'}), 200
            else:
                return jsonify({'error': 'Failed to delete video from storage'}), 500
                
    except Exception as e:
        logger.error(f"Failed to delete video: {str(e)}")
        return jsonify({'error': 'Failed to delete video'}), 500

@upload_bp.route('/<video_id>/status', methods=['GET'])
@login_required
def get_video_status(video_id):
    """Get video processing status"""
    try:
        with get_db_session() as db:
            video = db.query(Video).filter(
                Video.id == video_id,
                Video.user_id == session['user_id']
            ).first()
            
            if not video:
                return jsonify({'error': 'Video not found'}), 404
            
            return jsonify({
                'video_id': str(video.id),
                'status': video.status,
                'error_message': video.error_message
            }), 200
            
    except Exception as e:
        logger.error(f"Failed to get video status: {str(e)}")
        return jsonify({'error': 'Failed to get status'}), 500