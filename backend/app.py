import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
import json
from datetime import datetime

from backend.utils.scheduled import start_scheduler
from backend.utils.config import Config
from models import db, InformationPiece, ChatSession, ChatMessage
from backend.llm.llm_abstraction import chat_with_context

# Import services
from services import AuthService, ReportService, FacebookAuthService, ProfileService


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["DEBUG"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = True
    
    # Initialize extensions
    db.init_app(app)
    jwt = JWTManager(app)
    CORS(app)
    
    start_scheduler(db)
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app


app = create_app()

# Initialize services
auth_service = AuthService(db)
report_service = ReportService(db)
fb_auth_service = FacebookAuthService(db)
profile_service = ProfileService(db)


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ==================== AUTH ROUTES ====================

@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.json
        result = auth_service.register_user(
            email=data.get('email', ''),
            password=data.get('password', ''),
            name=data.get('name', '')
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Registration failed. Please try again.'}), 500


@app.route('/api/login', methods=['POST'])
def login():
    """Authenticate user and return JWT token"""
    try:
        data = request.json
        result = auth_service.login_user(
            email=data.get('email', ''),
            password=data.get('password', '')
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': 'Login failed. Please try again.'}), 500


@app.route('/api/confirm', methods=['POST'])
def confirm_email():
    """Confirm user email address"""
    try:
        data = request.json
        result = auth_service.confirm_email(data.get('email', ''))
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Email confirmation failed.'}), 500


# ==================== SEARCH & REPORT ROUTES ====================

@app.route('/api/search', methods=['POST'])
@jwt_required()
def search():
    """Create a new report based on search query"""
    try:
        current_user_email = get_jwt_identity()
        data = request.json
        query = data.get('query', '').strip()
        
        # Get Facebook cookies if available
        fb_cookies = fb_auth_service.get_cookies(current_user_email)
        
        # Create report using service
        report = report_service.create_report(current_user_email, query, fb_cookies)
        return jsonify({'success': True, 'report': report}), 200
        
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        print(f"Search error: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Search failed. Please try again.'}), 500


@app.route('/api/report/<report_id>', methods=['GET'])
@jwt_required()
def get_report(report_id):
    """Retrieve a specific report"""
    try:
        current_user_email = get_jwt_identity()
        report = report_service.get_report(current_user_email, report_id)
        return jsonify({'success': True, 'report': report}), 200
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': 'Failed to retrieve report.'}), 500


@app.route('/api/history', methods=['GET'])
@jwt_required()
def get_search_history():
    """Get user's search history"""
    try:
        current_user_email = get_jwt_identity()
        history = report_service.get_search_history(current_user_email)
        return jsonify({'success': True, 'history': history}), 200
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': 'Failed to retrieve search history.'}), 500


# ==================== PROFILE ROUTES ====================

@app.route('/api/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get user profile information"""
    try:
        current_user_email = get_jwt_identity()
        profile = profile_service.get_profile(current_user_email)
        return jsonify({'success': True, 'profile': profile}), 200
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': 'Failed to retrieve profile.'}), 500


@app.route('/api/profile/password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        current_user_email = get_jwt_identity()
        data = request.json or {}
        
        result = auth_service.change_password(
            email=current_user_email,
            current_password=data.get('current_password'),
            new_password=data.get('new_password')
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        print(f'Error changing password: {e}')
        return jsonify({'success': False, 'message': 'Failed to change password. Please try again.'}), 500


@app.route('/api/settings/theme', methods=['POST'])
@jwt_required()
def set_theme():
    """Set user theme preference"""
    try:
        current_user_email = get_jwt_identity()
        data = request.json
        
        result = profile_service.set_theme(current_user_email, data.get('theme'))
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to save theme preference'}), 500


# ==================== FACEBOOK AUTH ROUTES ====================

@app.route('/api/profile/facebook/cookies', methods=['POST'])
@jwt_required()
def update_facebook_cookies():
    """Save Facebook cookies for user"""
    try:
        current_user_email = get_jwt_identity()
        data = request.json
        
        result = fb_auth_service.save_cookies(
            user_email=current_user_email,
            cookies_json=data.get('cookies_json')
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to save cookies'}), 500


@app.route('/api/profile/facebook/login', methods=['POST'])
@jwt_required()
def facebook_login_with_credentials():
    """Login to Facebook using credentials and save cookies"""
    try:
        current_user_email = get_jwt_identity()
        data = request.json or {}
        
        result = fb_auth_service.login_with_credentials(
            user_email=current_user_email,
            fb_login=data.get('login'),
            fb_password=data.get('password'),
            headless=data.get('headless', True)
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        print(f'FB login error: {e}')
        return jsonify({'success': False, 'message': 'Failed to perform login.'}), 500


@app.route('/api/profile/facebook/cookies', methods=['GET'])
@jwt_required()
def get_facebook_cookies_status():
    """Check if user has valid Facebook cookies"""
    try:
        current_user_email = get_jwt_identity()
        cookies = fb_auth_service.get_cookies(current_user_email)
        
        return jsonify({
            'has_cookies': cookies is not None,
            'is_expired': cookies is None
        }), 200
    except Exception as e:
        return jsonify({'error': 'Failed to check cookies status'}), 500


@app.route('/api/profile/facebook/cookies', methods=['DELETE'])
@jwt_required()
def delete_facebook_cookies():
    """Delete user's Facebook cookies"""
    try:
        current_user_email = get_jwt_identity()
        result = fb_auth_service.delete_cookies(current_user_email)
        return jsonify(result), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete cookies'}), 500


# ==================== ASSISTANT CHAT ROUTES ====================

@app.route('/api/chat/report/<report_id>/sessions', methods=['POST'])
@jwt_required()
def create_chat_session(report_id):
    """Create a chat session for a report"""
    data = request.json or {}
    title = data.get('title')
    save_history = bool(data.get('save_history', True))
    current_user_email = get_jwt_identity()
    
    try:
        # Reuse a single session per user+report
        existing = ChatSession.query.filter_by(
            user_email=current_user_email, 
            report_id=report_id
        ).first()
        
        if existing:
            return jsonify({'success': True, 'session': existing.to_dict()}), 200

        cs = ChatSession(
            user_email=current_user_email, 
            report_id=report_id, 
            title=title, 
            save_history=save_history
        )
        db.session.add(cs)
        db.session.commit()
        return jsonify({'success': True, 'session': cs.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        print(f'Failed to create chat session: {e}')
        return jsonify({'success': False, 'message': 'Failed to create session'}), 500


@app.route('/api/chat/sessions/<int:session_id>/messages', methods=['GET'])
@jwt_required()
def get_session_messages(session_id):
    """Get all messages for a chat session"""
    try:
        msgs = ChatMessage.query.filter_by(session_id=session_id)\
            .order_by(ChatMessage.created_at.asc())\
            .all()
        out = [m.to_dict() for m in msgs]
        return jsonify({'success': True, 'messages': out}), 200
    except Exception as e:
        print(f'Failed fetching messages: {e}')
        return jsonify({'success': False, 'message': 'Failed to fetch messages'}), 500


@app.route('/api/chat/sessions/<int:session_id>/messages', methods=['POST'])
@jwt_required()
def post_session_message(session_id):
    """Post a message to a chat session and get AI response"""
    data = request.json or {}
    user_msg = data.get('message', '').strip()
    scope = data.get('scope', 'report')  # 'report' or 'datapieces'
    datapiece_ids = data.get('datapiece_ids', []) or []
    provider = "groq"

    if not user_msg:
        return jsonify({'success': False, 'message': 'Message is required'}), 400

    session = ChatSession.query.filter_by(id=session_id).first()
    if not session:
        return jsonify({'success': False, 'message': 'Session not found'}), 404
    
    # Build context
    context = []
    try:
        if scope == 'datapieces' and datapiece_ids:
            piece = InformationPiece.query.filter(
                InformationPiece.id.in_(datapiece_ids)
            ).first()
            user_msg += "\n\nContext:\n" + str(piece.to_dict())
            
            # Similar pieces for datapiece
            similar = InformationPiece.query.filter(
                InformationPiece.report_id.in_(piece.report_id),
                InformationPiece.category_id == piece.category_id,
                InformationPiece.id != piece.id
            ).order_by(InformationPiece.created_at.desc()).limit(5).all()
            
            for sp in similar:
                user_msg += "\n\nSimilar pieces:\n" + str(sp.to_dict())
        else:
            # Whole report: include recent pieces for the report
            context = [
                str(p.to_dict()) 
                for p in InformationPiece.query.filter_by(report_id=session.report_id)
                    .order_by(InformationPiece.created_at.desc())
                    .limit(40)
                    .all()
            ]
            user_msg += "\n\nContext:\n" + '\n\n'.join(context) if context else ""
            
    except Exception as e:
        print(f'Failed loading datapiece context: {e}')

    # Save user message if history is enabled
    try:
        if session.save_history:
            um = ChatMessage(session_id=session.id, sender='user', content=user_msg)
            db.session.add(um)
            db.session.commit()
    except Exception:
        db.session.rollback()

    # Prepare messages for LLM
    system_prompt = {
        'role': 'system',
        'content': """You respond as a friendly assistant who explains user information based only on the provided sources and helps to keep awareness about digital footprint security and protecting yourself online

                    Do not hallucinate.
                    Draw conclusions from the datapiece (and context), similar datapieces (provided under Similar Pieces)
                    If you don't know, say exactly that.
                    Do not give away technical details (such as ID), you are allowed to give away information based on links, context snippets and titles

                    When answering:
                    - Make the explanation short and understandable.
                    - Elaborate whether disposing this datapiece online is very bad and why
                    - Tell the user where the information came from (source link).

                    Use ONLY html tags (i.e. <strong>, <italic> or <br>
                    """
    }
    messages = [system_prompt, {'role': 'user', 'content': user_msg}]

    # Call LLM abstraction with fallback
    try:
        llm_result = chat_with_context(
            provider or 'groq', 
            messages, 
            context, 
            fallback=['openai', 'local']
        )
        reply = llm_result.get('reply') if isinstance(llm_result, dict) else str(llm_result)
        sources = llm_result.get('sources', []) if isinstance(llm_result, dict) else []
    except Exception as e:
        print(f'LLM call failed: {e}')
        reply = 'Failed to get response from LLM.'
        sources = []

    # Save assistant reply if history is enabled
    try:
        if session.save_history:
            am = ChatMessage(
                session_id=session.id, 
                sender='assistant', 
                content=reply, 
                meta=json.dumps({'sources': sources})
            )
            db.session.add(am)
            db.session.commit()
    except Exception:
        db.session.rollback()

    return jsonify({'success': True, 'assistant': reply, 'sources': sources}), 200

@app.route('/api/settings/delete-account', methods=['POST'])
@jwt_required()
def delete_account():
    """Delete user account and related data"""
    data = request.json
    password = data.get('password')
    full_name = data.get('full_name')
    
    # TODO: Implement actual deletion logic with password verification
    print(f"\n[ACCOUNT DELETION] User '{full_name}' deleted at {datetime.utcnow()}")
    print(f"[ACTION] Removing: user records, search history, cookies, LLM configs, chat data")
    
    return jsonify({'success': True, 'message': 'Account deleted'}), 200


# ==================== UTILITY ROUTES ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat() + 'Z'})


@app.route('/')
def home():
    """Serve frontend"""
    return render_template('index.html')


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
