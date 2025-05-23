from flask import Blueprint, request, jsonify, session, current_app
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
import subprocess
import json

logger = logging.getLogger(__name__)

upload_bp = Blueprint('upload', __name__)

# Allowed video extensions
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_video_metadata(file_path):
    """Extract video metadata using ffprobe"""
    try:
        # Check if ffprobe is available
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            
            # Extract relevant metadata
            format_info = data.get('format', {})
            video_stream = next((s for s in data.get('streams', []) if s['codec_type'] == 'video'), {})
            
            metadata = {
                'duration': float(format_info.get('duration', 0)),
                'file_size': int(format_info.get('size', 0)),
                'format': format_info.get('format_name', '').split(',')[0],
                'resolution': f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)}",
                'fps': eval(video_stream.get('r_frame_rate', '0/1')) if '/' in video_stream.get('r_frame_rate', '') else 0
            }
            
            return metadata
    except Exception as e:
        logger.warning(f"Could not extract video metadata: {str(e)}")
    
    return {
        'duration': None,
        'file_size': os.path.getsize(file_path),
        'format': None,
        'resolution': None,
        'fps': None
    }

def generate_thumbnail(video_path, output_path):
    """Generate thumbnail from video"""
    try:
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-ss', '00:00:01',  # Capture at 1 second
            '-vframes', '1',
            '-vf', 'scale=320:-1',  # Width 320px, maintain aspect ratio
            '-y',  # Overwrite output
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True
    except Exception as e:
        logger.warning(f"Could not generate thumbnail: {str(e)}")
    
    return False

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
        
        # Check file size (if provided)
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 500 * 1024 * 1024)
        if request.content_length and request.content_length > max_size:
            return jsonify({'error': f'File too large. Maximum size is {max_size // (1024*1024)}MB'}), 413
        
        # Get video metadata from request
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        tags = request.form.getlist('tags[]')  # Array of tags
        
        if not title:
            title = file.filename.rsplit('.', 1)[0]  # Use filename as title if not provided
        
        # Get file information
        filename = secure_filename(file.filename)
        extension = filename.rsplit('.', 1)[1].lower()
        
        # Generate unique S3 key
        video_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        s3_key = f"videos/{session['user_id']}/{timestamp}_{video_id}.{extension}"
        
        # Save file temporarily
        temp_dir = current_app.config.get('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'temp'))
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{video_id}.{extension}")
        file.save(temp_path)
        
        try:
            # Extract video metadata
            metadata = get_video_metadata(temp_path)
            
            # Generate thumbnail
            thumbnail_path = os.path.join(temp_dir, f"{video_id}_thumb.jpg")
            thumbnail_s3_key = f"thumbnails/{session['user_id']}/{timestamp}_{video_id}_thumb.jpg"
            thumbnail_generated = generate_thumbnail(temp_path, thumbnail_path)
            
            # Upload to S3
            logger.info(f"Uploading video to S3: {s3_key}")
            
            # Emit status update
            if hasattr(current_app, 'socketio'):
                current_app.socketio.emit('upload_status', {
                    'video_id': video_id,
                    'status': 'uploading',
                    'message': 'Uploading to cloud storage...'
                }, room=f'user_{session["user_id"]}')
            
            s3_url = aws_service.upload_video_to_s3(temp_path, s3_key)
            
            # Upload thumbnail if generated
            thumbnail_url = None
            if thumbnail_generated and os.path.exists(thumbnail_path):
                try:
                    thumbnail_url = aws_service.upload_video_to_s3(thumbnail_path, thumbnail_s3_key)
                    os.remove(thumbnail_path)
                except Exception as e:
                    logger.warning(f"Failed to upload thumbnail: {str(e)}")
            
            # Create database entry
            with get_db_session() as db:
                new_video = Video(
                    id=uuid.UUID(video_id),
                    user_id=session['user_id'],
                    title=title,
                    description=description,
                    filename=filename,
                    s3_key=s3_key,
                    s3_url=s3_url,
                    thumbnail_url=thumbnail_url,
                    file_size=metadata['file_size'],
                    duration=metadata['duration'],
                    format=metadata['format'] or extension,
                    resolution=metadata['resolution'],
                    fps=metadata['fps'],
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
                if hasattr(current_app, 'socketio'):
                    current_app.socketio.emit('upload_complete', {
                        'video_id': str(new_video.id),
                        'status': 'uploaded',
                        'message': 'Video uploaded successfully. Processing started.',
                        'video': new_video.to_dict()
                    }, room=f'user_{session["user_id"]}')
                
                logger.info(f"Video uploaded successfully: {video_id}")
                
                return jsonify({
                    'message': 'Video uploaded successfully',
                    'video': new_video.to_dict()
                }), 201
                
        except Exception as e:
            # Clean up temp files on error
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if 'thumbnail_path' in locals() and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            raise e
            
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        
        # Emit error status
        if hasattr(current_app, 'socketio') and 'video_id' in locals():
            current_app.socketio.emit('upload_error', {
                'video_id': video_id,
                'status': 'failed',
                'error': str(e)
            }, room=f'user_{session["user_id"]}')
        
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@upload_bp.route('/', methods=['GET'])
@login_required
def get_user_videos():
    """Get all videos for the current user"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        per_page = min(per_page, 100)  # Limit max per page
        
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
            presigned_url = aws_service.generate_presigned_url(video.s3_key, expiration=3600)
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
            deleted_video = aws_service.delete_video_from_s3(video.s3_key)
            
            # Delete thumbnail if exists
            if video.thumbnail_url:
                thumbnail_key = video.thumbnail_url.split('/')[-3:]  # Extract key from URL
                thumbnail_key = '/'.join(thumbnail_key)
                aws_service.delete_video_from_s3(thumbnail_key)
            
            # Delete from database
            db.delete(video)
            db.commit()
            
            logger.info(f"Video deleted: {video_id}")
            
            return jsonify({'message': 'Video deleted successfully'}), 200
                
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
                'error_message': video.error_message,
                'processing_started_at': video.processing_started_at.isoformat() if video.processing_started_at else None,
                'processing_completed_at': video.processing_completed_at.isoformat() if video.processing_completed_at else None
            }), 200
            
    except Exception as e:
        logger.error(f"Failed to get video status: {str(e)}")
        return jsonify({'error': 'Failed to get status'}), 500