from flask import Blueprint, request, jsonify, session
from functools import wraps
from backend.models.user import User
from backend.utils.database import get_db_session
import re

auth_bp = Blueprint('auth', __name__)

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, "Valid password"

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        # Validate input
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        full_name = data.get('name', '').strip()
        
        # Validate email
        if not email or not validate_email(email):
            return jsonify({'error': 'Invalid email address'}), 400
        
        # Validate password
        is_valid, message = validate_password(password)
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # Check if user exists
        with get_db_session() as db:
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                return jsonify({'error': 'Email already registered'}), 409
            
            # Create username from email
            username = email.split('@')[0]
            counter = 1
            base_username = username
            
            # Ensure unique username
            while db.query(User).filter(User.username == username).first():
                username = f"{base_username}{counter}"
                counter += 1
            
            # Create new user
            new_user = User(
                email=email,
                username=username,
                full_name=full_name
            )
            new_user.set_password(password)
            
            db.add(new_user)
            db.commit()
            
            return jsonify({
                'message': 'User registered successfully',
                'user': new_user.to_dict()
            }), 201
            
    except Exception as e:
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        with get_db_session() as db:
            user = db.query(User).filter(User.email == email).first()
            
            if not user or not user.check_password(password):
                return jsonify({'error': 'Invalid email or password'}), 401
            
            if not user.is_active:
                return jsonify({'error': 'Account is deactivated'}), 403
            
            # Set session
            session['user_id'] = user.id
            session['email'] = user.email
            session.permanent = True
            
            return jsonify({
                'message': 'Login successful',
                'user': user.to_dict()
            }), 200
            
    except Exception as e:
        return jsonify({'error': f'Login failed: {str(e)}'}), 500

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Logout user"""
    try:
        session.clear()
        return jsonify({'message': 'Logged out successfully'}), 200
    except Exception as e:
        return jsonify({'error': f'Logout failed: {str(e)}'}), 500

@auth_bp.route('/profile', methods=['GET'])
@login_required
def get_profile():
    """Get current user profile"""
    try:
        with get_db_session() as db:
            user = db.query(User).filter(User.id == session['user_id']).first()
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            return jsonify({'user': user.to_dict()}), 200
            
    except Exception as e:
        return jsonify({'error': f'Failed to get profile: {str(e)}'}), 500

@auth_bp.route('/profile', methods=['PUT'])
@login_required
def update_profile():
    """Update user profile"""
    try:
        data = request.get_json()
        
        with get_db_session() as db:
            user = db.query(User).filter(User.id == session['user_id']).first()
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Update allowed fields
            if 'full_name' in data:
                user.full_name = data['full_name'].strip()
            
            if 'password' in data:
                is_valid, message = validate_password(data['password'])
                if not is_valid:
                    return jsonify({'error': message}), 400
                user.set_password(data['password'])
            
            db.commit()
            
            return jsonify({
                'message': 'Profile updated successfully',
                'user': user.to_dict()
            }), 200
            
    except Exception as e:
        return jsonify({'error': f'Failed to update profile: {str(e)}'}), 500

@auth_bp.route('/check', methods=['GET'])
def check_auth():
    """Check if user is authenticated"""
    if 'user_id' in session:
        return jsonify({'authenticated': True, 'user_id': session['user_id']}), 200
    return jsonify({'authenticated': False}), 200