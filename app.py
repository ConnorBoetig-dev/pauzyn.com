from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import sys
from dotenv import load_dotenv
from datetime import timedelta
import logging

# Add the parent directory to Python path to fix imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Enable CORS for frontend communication
CORS(app, supports_credentials=True, origins=["http://localhost:3000", "http://localhost:5000", "http://127.0.0.1:5000"])

# WebSocket support for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Import and register blueprints
try:
    from backend.routes.auth import auth_bp
    from backend.routes.upload import upload_bp
    from backend.routes.search import search_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(upload_bp, url_prefix='/api/videos')
    app.register_blueprint(search_bp, url_prefix='/api/search')
except ImportError as e:
    logger.error(f"Failed to import routes: {e}")
    # Continue without routes for now

# Basic routes
@app.route('/')
def index():
    return jsonify({
        "message": "AI Video Gallery API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "auth": "/api/auth/*",
            "videos": "/api/videos/*",
            "search": "/api/search/*",
            "health": "/api/health"
        }
    })

@app.route('/api/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        from backend.utils.database import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return jsonify({
        "status": "healthy",
        "database": db_status,
        "uptime": "running"
    })

# WebSocket events for real-time updates
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f'Client connected: {request.sid}')
    emit('connected', {'message': 'Successfully connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f'Client disconnected: {request.sid}')

@socketio.on('join_user_room')
def handle_join_user_room(data):
    """Join user-specific room for personalized updates"""
    user_id = data.get('user_id')
    if user_id:
        room = f'user_{user_id}'
        join_room(room)
        logger.info(f'User {user_id} joined room: {room}')
        emit('joined_room', {'room': room})

@socketio.on('leave_user_room')
def handle_leave_user_room(data):
    """Leave user-specific room"""
    user_id = data.get('user_id')
    if user_id:
        room = f'user_{user_id}'
        leave_room(room)
        logger.info(f'User {user_id} left room: {room}')

@socketio.on('processing_status')
def handle_processing_status(data):
    """Request processing status for a video"""
    video_id = data.get('video_id')
    user_id = data.get('user_id')
    
    if video_id and user_id:
        # TODO: Get actual status from database
        emit('status_update', {
            'video_id': video_id,
            'status': 'processing',
            'progress': 45
        })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Internal server error: {str(error)}')
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(413)
def file_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 500MB'}), 413

# Initialize the app
def create_app():
    """Application factory pattern"""
    with app.app_context():
        # Initialize database tables
        try:
            from backend.utils.database import init_db
            init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            logger.info("Continuing without database initialization...")
    
    return app

if __name__ == '__main__':
    # Create the application
    app = create_app()
    
    # Run with SocketIO
    socketio.run(
        app, 
        debug=os.getenv('DEBUG', 'True').lower() == 'true',
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000))
    )