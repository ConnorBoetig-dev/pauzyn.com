from flask import Blueprint, request, jsonify
from backend.routes.auth import login_required

search_bp = Blueprint('search', __name__)

@search_bp.route('/', methods=['POST'])
@login_required
def search_videos():
    """Search videos using natural language"""
    # TODO: Implement search functionality
    return jsonify({
        'message': 'Search endpoint - Coming soon',
        'results': []
    }), 200

@search_bp.route('/suggestions', methods=['GET'])
@login_required
def get_suggestions():
    """Get search suggestions"""
    # TODO: Implement suggestions
    return jsonify({
        'suggestions': []
    }), 200