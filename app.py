from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# Enable CORS for frontend communication
CORS(app)

# WebSocket support for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*")

# Basic routes
@app.route('/')
def index():
    return jsonify({"message": "AI Video Gallery API", "status": "running"})

@app.route('/api/health')
def health_check():
    return jsonify({"status": "healthy"})

# Authentication routes
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    # TODO: Implement user registration
    return jsonify({"message": "Registration endpoint"})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    # TODO: Implement user login
    return jsonify({"message": "Login endpoint"})

# Upload routes
@app.route('/api/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # TODO: Implement video upload to S3 and trigger processing
    return jsonify({"message": "Upload endpoint", "filename": file.filename})

# Search routes
@app.route('/api/search', methods=['POST'])
def search_videos():
    data = request.get_json()
    query = data.get('query', '')
    
    # TODO: Implement vector search
    return jsonify({"message": "Search endpoint", "query": query})

# WebSocket events
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)