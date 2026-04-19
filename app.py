"""
========================================
EARNHUB - FLASK BACKEND API
========================================

Backend API for EarnHub Platform
- Handles user management
- Processes task completions
- Manages withdraw requests
- Telegram bot integration
- Admin functions

Requirements:
pip install flask firebase-admin python-telegram-bot requests
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import json
import os
from functools import wraps
import hashlib
import hmac

# Firebase imports
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import firestore

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
import logging

# ========================================
# INITIALIZATION
# ========================================

app = Flask(__name__)
CORS(app)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Firebase initialization
# Replace with your service account JSON path
try:
    cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://your-project.firebaseio.com'
    })
    fb = firestore.client()
    print('Firebase initialized successfully')
except Exception as e:
    print(f'Firebase initialization error: {e}')
    fb = None

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN')
ADMIN_SECRET = os.getenv('ADMIN_SECRET', 'your-secret-key')
MIN_WITHDRAW = 100
MAX_WITHDRAW = 100000

# ========================================
# AUTHENTICATION DECORATORS
# ========================================

def token_required(f):
    """Check if valid token is provided"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            # In production, verify JWT token
            # For now, we'll use simple validation
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'message': str(e)}), 401
    
    return decorated

def admin_required(f):
    """Check if admin token is provided"""
    @wraps(f)
    def decorated(*args, **kwargs):
        admin_token = request.headers.get('X-Admin-Token')
        
        if not admin_token or admin_token != ADMIN_SECRET:
            return jsonify({'message': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    
    return decorated

# ========================================
# USER MANAGEMENT ENDPOINTS
# ========================================

@app.route('/api/user/register', methods=['POST'])
def register_user():
    """Register new user"""
    try:
        data = request.get_json()
        
        required_fields = ['id', 'name', 'provider']
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'Missing required fields'}), 400
        
        user_id = data['id']
        
        # Check if user already exists
        user_doc = fb.collection('users').document(user_id).get()
        
        if user_doc.exists:
            return jsonify({
                'message': 'User already registered',
                'user': user_doc.to_dict()
            }), 200
        
        # Create user
        referral_code = generate_referral_code(user_id)
        
        user_data = {
            'id': user_id,
            'name': data['name'],
            'email': data.get('email', ''),
            'provider': data['provider'],
            'balance': 0,
            'totalEarned': 0,
            'referralCode': referral_code,
            'referredBy': data.get('referredBy', None),
            'createdAt': datetime.now(),
            'lastActive': datetime.now(),
            'status': 'active'
        }
        
        fb.collection('users').document(user_id).set(user_data)
        
        # Process referral bonus if applicable
        if data.get('referredBy'):
            process_referral(data['referredBy'], user_id)
        
        return jsonify({
            'message': 'User registered successfully',
            'user': user_data
        }), 201
    
    except Exception as e:
        logger.error(f'Registration error: {e}')
        return jsonify({'message': str(e)}), 500

@app.route('/api/user/<user_id>', methods=['GET'])
@token_required
def get_user(user_id):
    """Get user data"""
    try:
        user_doc = fb.collection('users').document(user_id).get()
        
        if not user_doc.exists:
            return jsonify({'message': 'User not found'}), 404
        
        user_data = user_doc.to_dict()
        
        # Convert datetime objects to strings
        if isinstance(user_data.get('createdAt'), datetime):
            user_data['createdAt'] = user_data['createdAt'].isoformat()
        if isinstance(user_data.get('lastActive'), datetime):
            user_data['lastActive'] = user_data['lastActive'].isoformat()
        
        return jsonify(user_data), 200
    
    except Exception as e:
        logger.error(f'Get user error: {e}')
        return jsonify({'message': str(e)}), 500

@app.route('/api/user/<user_id>/balance', methods=['PUT'])
@token_required
def update_balance(user_id):
    """Update user balance"""
    try:
        data = request.get_json()
        
        if 'amount' not in data:
            return jsonify({'message': 'Amount is required'}), 400
        
        user_ref = fb.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return jsonify({'message': 'User not found'}), 404
        
        current_balance = user_doc.get('balance', 0)
        new_balance = current_balance + data['amount']
        
        user_ref.update({
            'balance': new_balance,
            'lastActive': datetime.now()
        })
        
        return jsonify({
            'message': 'Balance updated',
            'newBalance': new_balance
        }), 200
    
    except Exception as e:
        logger.error(f'Update balance error: {e}')
        return jsonify({'message': str(e)}), 500

# ========================================
# TASK MANAGEMENT ENDPOINTS
# ========================================

@app.route('/api/tasks', methods=['GET'])
def get_all_tasks():
    """Get all available tasks"""
    try:
        tasks = {
            'videos': [],
            'ads': [],
            'apps': [],
            'channels': []
        }
        
        # Fetch each task type
        for task_type in ['video', 'ads', 'apps', 'channels']:
            try:
                docs = fb.collection('tasks').document(task_type).collection('items').stream()
                tasks[task_type + 's'] = [doc.to_dict() for doc in docs if doc.to_dict().get('status') == 'active']
            except:
                pass
        
        return jsonify(tasks), 200
    
    except Exception as e:
        logger.error(f'Get tasks error: {e}')
        return jsonify({'message': str(e)}), 500

@app.route('/api/task/complete', methods=['POST'])
@token_required
def complete_task():
    """Mark task as completed"""
    try:
        data = request.get_json()
        
        required_fields = ['userId', 'taskId', 'taskType']
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'Missing required fields'}), 400
        
        user_id = data['userId']
        task_id = data['taskId']
        task_type = data['taskType']
        
        # Check if already completed
        completion_query = fb.collection('completions').where(
            'userId', '==', user_id
        ).where(
            'taskId', '==', task_id
        ).stream()
        
        if list(completion_query):
            return jsonify({'message': 'Task already completed'}), 400
        
        # Get task details
        task_doc = None
        try:
            task_doc = fb.collection('tasks').document(task_type).collection('items').document(task_id).get()
        except:
            pass
        
        if not task_doc or not task_doc.exists:
            return jsonify({'message': 'Task not found'}), 404
        
        task_data = task_doc.to_dict()
        reward = task_data.get('reward', 0)
        
        # Record completion
        fb.collection('completions').add({
            'userId': user_id,
            'taskId': task_id,
            'taskType': task_type,
            'reward': reward,
            'completedAt': datetime.now(),
            'ipAddress': request.remote_addr
        })
        
        # Update user balance
        user_ref = fb.collection('users').document(user_id)
        user_doc = user_ref.get()
        current_balance = user_doc.get('balance', 0)
        
        user_ref.update({
            'balance': current_balance + reward,
            'totalEarned': user_doc.get('totalEarned', 0) + reward,
            'lastActive': datetime.now()
        })
        
        return jsonify({
            'message': 'Task completed',
            'reward': reward
        }), 200
    
    except Exception as e:
        logger.error(f'Complete task error: {e}')
        return jsonify({'message': str(e)}), 500

# ========================================
# WITHDRAW MANAGEMENT ENDPOINTS
# ========================================

@app.route('/api/withdraw/request', methods=['POST'])
@token_required
def request_withdraw():
    """Create withdraw request"""
    try:
        data = request.get_json()
        
        required_fields = ['userId', 'amount', 'method', 'account']
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'Missing required fields'}), 400
        
        amount = float(data['amount'])
        
        # Validate amount
        if amount < MIN_WITHDRAW or amount > MAX_WITHDRAW:
            return jsonify({
                'message': f'Amount must be between ₹{MIN_WITHDRAW} and ₹{MAX_WITHDRAW}'
            }), 400
        
        # Validate method
        valid_methods = ['bkash', 'nagad', 'payoneer']
        if data['method'] not in valid_methods:
            return jsonify({'message': 'Invalid payment method'}), 400
        
        user_id = data['userId']
        user_doc = fb.collection('users').document(user_id).get()
        
        if not user_doc.exists:
            return jsonify({'message': 'User not found'}), 404
        
        user_data = user_doc.to_dict()
        if user_data['balance'] < amount:
            return jsonify({'message': 'Insufficient balance'}), 400
        
        # Create withdraw request
        withdraw_data = {
            'userId': user_id,
            'amount': amount,
            'method': data['method'],
            'account': data['account'],
            'status': 'pending',
            'createdAt': datetime.now(),
            'processedAt': None,
            'adminNotes': ''
        }
        
        withdraw_ref = fb.collection('withdraws').add(withdraw_data)
        
        # Deduct from balance
        fb.collection('users').document(user_id).update({
            'balance': user_data['balance'] - amount
        })
        
        return jsonify({
            'message': 'Withdraw request created',
            'withdrawId': withdraw_ref[1].id
        }), 201
    
    except Exception as e:
        logger.error(f'Withdraw request error: {e}')
        return jsonify({'message': str(e)}), 500

@app.route('/api/withdraw/<user_id>', methods=['GET'])
@token_required
def get_user_withdraws(user_id):
    """Get user's withdraw history"""
    try:
        withdraws_query = fb.collection('withdraws').where(
            'userId', '==', user_id
        ).order_by(
            'createdAt', direction=firestore.Query.DESCENDING
        ).stream()
        
        withdraws = []
        for doc in withdraws_query:
            withdraw = doc.to_dict()
            # Convert datetime
            if isinstance(withdraw.get('createdAt'), datetime):
                withdraw['createdAt'] = withdraw['createdAt'].isoformat()
            withdraws.append(withdraw)
        
        return jsonify(withdraws), 200
    
    except Exception as e:
        logger.error(f'Get withdraws error: {e}')
        return jsonify({'message': str(e)}), 500

# ========================================
# ADMIN ENDPOINTS
# ========================================

@app.route('/api/admin/dashboard', methods=['GET'])
@admin_required
def admin_dashboard():
    """Get admin dashboard stats"""
    try:
        users = fb.collection('users').stream()
        withdraws = fb.collection('withdraws').where('status', '==', 'pending').stream()
        completions = fb.collection('completions').stream()
        
        users_list = [user.to_dict() for user in users]
        withdraws_list = list(withdraws)
        completions_list = list(completions)
        
        total_earnings = sum(user.get('totalEarned', 0) for user in users_list)
        
        stats = {
            'totalUsers': len(users_list),
            'totalEarnings': total_earnings,
            'pendingWithdraws': len(withdraws_list),
            'totalCompletions': len(completions_list)
        }
        
        return jsonify(stats), 200
    
    except Exception as e:
        logger.error(f'Dashboard error: {e}')
        return jsonify({'message': str(e)}), 500

@app.route('/api/admin/withdraws', methods=['GET'])
@admin_required
def get_all_withdraws():
    """Get all withdraw requests"""
    try:
        status = request.args.get('status', 'pending')
        
        withdraws_query = fb.collection('withdraws').where(
            'status', '==', status
        ).stream()
        
        withdraws = []
        for doc in withdraws_query:
            withdraw = doc.to_dict()
            withdraw['id'] = doc.id
            withdraws.append(withdraw)
        
        return jsonify(withdraws), 200
    
    except Exception as e:
        logger.error(f'Get withdraws error: {e}')
        return jsonify({'message': str(e)}), 500

@app.route('/api/admin/withdraw/<withdraw_id>/approve', methods=['PUT'])
@admin_required
def approve_withdraw(withdraw_id):
    """Approve withdraw request"""
    try:
        fb.collection('withdraws').document(withdraw_id).update({
            'status': 'approved',
            'processedAt': datetime.now()
        })
        
        return jsonify({'message': 'Withdraw approved'}), 200
    
    except Exception as e:
        logger.error(f'Approve withdraw error: {e}')
        return jsonify({'message': str(e)}), 500

@app.route('/api/admin/withdraw/<withdraw_id>/reject', methods=['PUT'])
@admin_required
def reject_withdraw(withdraw_id):
    """Reject withdraw request"""
    try:
        data = request.get_json()
        reason = data.get('reason', 'No reason provided')
        
        # Get withdraw details
        withdraw_doc = fb.collection('withdraws').document(withdraw_id).get()
        withdraw = withdraw_doc.to_dict()
        
        # Refund balance to user
        user_ref = fb.collection('users').document(withdraw['userId'])
        user_doc = user_ref.get()
        user_data = user_doc.to_dict()
        
        user_ref.update({
            'balance': user_data['balance'] + withdraw['amount']
        })
        
        # Update withdraw status
        fb.collection('withdraws').document(withdraw_id).update({
            'status': 'rejected',
            'processedAt': datetime.now(),
            'adminNotes': reason
        })
        
        return jsonify({'message': 'Withdraw rejected and balance refunded'}), 200
    
    except Exception as e:
        logger.error(f'Reject withdraw error: {e}')
        return jsonify({'message': str(e)}), 500

@app.route('/api/admin/task/add', methods=['POST'])
@admin_required
def add_task():
    """Add new task"""
    try:
        data = request.get_json()
        
        required_fields = ['taskType', 'title', 'description', 'reward']
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'Missing required fields'}), 400
        
        task_type = data['taskType']
        task_id = f"{task_type}_{int(datetime.now().timestamp())}"
        
        task_data = {
            'id': task_id,
            'title': data['title'],
            'description': data['description'],
            'reward': data['reward'],
            'url': data.get('url', ''),
            'status': 'active',
            'createdAt': datetime.now()
        }
        
        fb.collection('tasks').document(task_type).collection('items').document(task_id).set(task_data)
        
        return jsonify({
            'message': 'Task created',
            'taskId': task_id
        }), 201
    
    except Exception as e:
        logger.error(f'Add task error: {e}')
        return jsonify({'message': str(e)}), 500

@app.route('/api/admin/task/<task_type>/<task_id>', methods=['DELETE'])
@admin_required
def delete_task(task_type, task_id):
    """Delete task"""
    try:
        fb.collection('tasks').document(task_type).collection('items').document(task_id).delete()
        
        return jsonify({'message': 'Task deleted'}), 200
    
    except Exception as e:
        logger.error(f'Delete task error: {e}')
        return jsonify({'message': str(e)}), 500

# ========================================
# UTILITY FUNCTIONS
# ========================================

def generate_referral_code(user_id):
    """Generate unique referral code"""
    return hashlib.md5(f'{user_id}{datetime.now()}'.encode()).hexdigest()[:10].upper()

def process_referral(referrer_id, referred_id):
    """Process referral bonus"""
    try:
        referrer_doc = fb.collection('users').document(referrer_id).get()
        if referrer_doc.exists:
            referrer = referrer_doc.to_dict()
            bonus = 20  # Points
            
            fb.collection('users').document(referrer_id).update({
                'balance': referrer['balance'] + bonus,
                'totalEarned': referrer['totalEarned'] + bonus
            })
            
            # Record referral
            fb.collection('referrals').add({
                'referrerId': referrer_id,
                'referredUserId': referred_id,
                'bonusAmount': bonus,
                'createdAt': datetime.now()
            })
    except Exception as e:
        logger.error(f'Process referral error: {e}')

# ========================================
# ERROR HANDLERS
# ========================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'message': 'Internal server error'}), 500

# ========================================
# HEALTH CHECK
# ========================================

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

# ========================================
# RUN SERVER
# ========================================

if __name__ == '__main__':
    # Development
    app.run(debug=True, host='0.0.0.0', port=5000)
    
    # For production, use gunicorn:
    # gunicorn -w 4 -b 0.0.0.0:5000 app:app
    
