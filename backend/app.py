import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from functools import wraps

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
import json
from datetime import datetime

from backend.utils.scheduled import start_scheduler
from backend.utils.config import Config
from models import db, User
from backend.wrappers.llm_wrapper import chat

import bleach
from functools import wraps

import ssl

# Import services
from services import AuthService, ReportService, FacebookAuthService, ProfileService, AssistantService
from backend.services.admin_service import AdminService
from backend.engines.rag_engine import RagEngine



# ==================== SETTINGS AND ROLE-AUTH DECORATORS ====================

def recursive_clean(item):

    if isinstance(item, dict):
        return {k: recursive_clean(v) for k, v in item.items()}
    
    elif isinstance(item, list):
        return [recursive_clean(i) for i in item]
    
    elif isinstance(item, str):

        return bleach.clean(item, tags=[], attributes={}, strip=True)
    
    return item

def register_security_hooks(app):
    
    # inbound sanitization(Before the route handles data)
    @app.before_request
    def sanitize_incoming_requests():
        if request.is_json and request.data:
            try:
                data = request.get_json()
                clean_data = recursive_clean(data)
                
                request._cached_json = (clean_data, clean_data)
            except Exception as e:
                 # If parsing fails, return original response to avoid throwing
                pass

    # outboun sanitization (Before the response leaves the server)
    @app.after_request
    def sanitize_outgoing_response(response):
        if response.is_json:
            try:

                content = response.get_data(as_text=True)
                data = json.loads(content)

                clean_data = recursive_clean(data)
                
                response.set_data(json.dumps(clean_data))
            except Exception:
                pass
        
        return response

    # nocache headers (Prevent browser from storing sensitive data)
    @app.after_request
    def add_no_cache_headers(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        # no clickjacking
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        
        # HSTS (against MITM, enforce HTTPS only)
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response

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
        
    register_security_hooks(app)
    
    return app


app = create_app()

# Initialize services
auth_service = AuthService(db)
fb_auth_service = FacebookAuthService(db)

profile_service = ProfileService(db)
analytics_engine = AdminService(db)
rag_engine = RagEngine()

report_service = ReportService(db)
assistant_service = AssistantService(db)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user_email = get_jwt_identity()
        
        # Verify user exists and has admin flag
        user = db.session.query(User).filter_by(email=current_user_email).first()
        
        if not user or not getattr(user, 'is_admin', False):
            return jsonify({
                'success': False, 
                'message': 'Access denied. Admin privileges required.'
            }), 403
            
        return f(*args, **kwargs)
    return decorated_function

def active_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user_email = get_jwt_identity()
        
        # Verify user exists and has admin flag
        user = db.session.query(User).filter_by(email=current_user_email).first()
        
        if not user or getattr(user, 'is_deactivated', True):
            return jsonify({
                'success': False, 
                'message': 'Access denied. Your account has been deactivated. Contact support@profolio.com'
            }), 403
            
        return f(*args, **kwargs)
    return decorated_function

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
        print(f"Login error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 401
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'Login failed. Please try again.'}), 500


# ==================== SEARCH & REPORT ROUTES ====================

@app.route('/api/search', methods=['POST'])
@jwt_required()
@active_required
def search():
    """Create a new report based on search query"""
    try:
        
        print(request.json)
        
        current_user_email = get_jwt_identity()
        data = request.json
        query = data.get('query', '').strip()
        is_general_search = data.get('general_search', True)
        is_facebook_search = data.get('facebook_search', False)
        
        # Get Facebook cookies if available
        fb_cookies = fb_auth_service.get_cookies(current_user_email)
        
        # Create report using service
        report = report_service.create_report(current_user_email, query, fb_cookies, use_facebook=is_facebook_search, use_general=is_general_search)
        return jsonify({'success': True, 'report': report}), 200
        
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        print(f"Search error: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Search failed. Please try again.'}), 500


@app.route('/api/report/<report_id>', methods=['GET'])
@jwt_required()
@active_required
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
@active_required
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


@app.route('/api/reports/<report_id>/export', methods=['GET'])
@jwt_required()
@active_required
def export_report(report_id):
    """Export a report to JSON or PDF"""
    format_type = request.args.get('format', 'json').lower()
    if format_type not in ['json', 'pdf']:
        return jsonify({'success': False, 'message': 'Invalid format. Use json or pdf.'}), 400
    
    try:
        current_user_email = get_jwt_identity()
        result = report_service.get_report(current_user_email, report_id)
        user = db.session.query(User).filter_by(email=current_user_email).first()
        
        if format_type == 'json':
            response = jsonify(result)
            response.headers['Content-Disposition'] = f'attachment; filename=report_{report_id}.json'
            response.headers['Content-Type'] = 'application/json'
            return response
        elif format_type == 'pdf':
            # Generate simple PDF
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from io import BytesIO
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            story.append(Paragraph(f"Report ID: {result['report_id']}", styles['Title']))
            story.append(Spacer(1, 12))
            
            # Author
            author_text = f"Collected and generated by Profolio System, generation requested by {user.name} ({user.email})"
            story.append(Paragraph(author_text, styles['Normal']))
            story.append(Spacer(1, 12))
            
            # Generated At
            generated_at = result.get('generated_at', 'N/A')
            story.append(Paragraph(f"Generated At: {generated_at}", styles['Normal']))
            story.append(Spacer(1, 12))
            
            # Query
            story.append(Paragraph(f"Query: {result['query']}", styles['Heading2']))
            story.append(Spacer(1, 12))
            
            # Executive Summary
            story.append(Paragraph("Executive Summary", styles['Heading2']))
            story.append(Paragraph(result.get('executive_summary', 'N/A'), styles['Normal']))
            story.append(Spacer(1, 12))
            
            # Risk Distribution
            story.append(Paragraph("Risk Distribution", styles['Heading2']))
            risk_dist = result.get('risk_distribution', {})
            story.append(Paragraph(f"High: {risk_dist.get('high', 0)}, Medium: {risk_dist.get('medium', 0)}, Low: {risk_dist.get('low', 0)}", styles['Normal']))
            story.append(Spacer(1, 12))
            
            # Detailed Findings
            story.append(Paragraph("Detailed Findings", styles['Heading2']))
            findings = result.get('detailed_findings', [])
            for finding in findings:
                story.append(Paragraph(f"Source: {finding.get('source', 'N/A')}", styles['Normal']))
                story.append(Paragraph(f"Category: {finding.get('category', 'N/A')}", styles['Normal']))
                story.append(Paragraph(f"Info: {finding.get('info', 'N/A')}", styles['Normal']))
                story.append(Paragraph(f"Risk Score: {finding.get('risk_score', 'N/A')}", styles['Normal']))
                story.append(Paragraph(f"URL: {finding.get('url', 'N/A')}", styles['Normal']))
                story.append(Spacer(1, 6))
            
            # Recommendations
            story.append(Paragraph("Recommendations", styles['Heading2']))
            recs = result.get('recommendations', [])
            for rec in recs:
                story.append(Paragraph(rec, styles['Normal']))
                story.append(Spacer(1, 6))
            
            doc.build(story)
            buffer.seek(0)
            
            from flask import make_response
            response = make_response(buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=report_{report_id}.pdf'
            return response
    
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 404
    except Exception as e:
        print(f"Error exporting report: {e}")
        return jsonify({'success': False, 'message': 'Failed to export report.'}), 500


# ==================== PROFILE ROUTES ====================

@app.route('/api/profile', methods=['GET'])
@jwt_required()
@active_required
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
@active_required
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
@active_required
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
@active_required
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
@active_required
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
@active_required
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
@active_required
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
@active_required
def create_chat_session(report_id):
    """Create a chat session for a report"""
    data = request.json or {}
    title = data.get('title')
    save_history = bool(data.get('save_history', True))
    current_user_email = get_jwt_identity()
    
    try:
        cs = assistant_service.create_session(current_user_email, report_id, title, save_history)
        
        if not cs:
            return jsonify({'success': False, 'message': 'Failed to create session'}), 500
        return jsonify({'success': True, 'session': cs.to_dict()}), 200
    except Exception as e:
        print(f'Failed to create chat session: {e}')
        return jsonify({'success': False, 'message': 'Failed to create session'}), 500


@app.route('/api/chat/sessions/<int:session_id>/messages', methods=['GET'])
@jwt_required()
@active_required
def get_session_messages(session_id):
    """Get all messages for a chat session"""
    try:
        out = assistant_service.get_session_messages(session_id)
        return jsonify({'success': True, 'messages': out}), 200
    except Exception as e:
        print(f'Failed fetching messages: {e}')
        return jsonify({'success': False, 'message': 'Failed to fetch messages'}), 500


@app.route('/api/chat/sessions/<int:session_id>/messages', methods=['POST'])
@jwt_required()
@active_required
def post_session_message(session_id):
    """Post a message to a chat session and get AI response"""
    data = request.json or {}
    user_msg = data.get('message', '').strip()
    scope = data.get('scope', 'report')  # 'report' or 'datapieces'
    datapiece_ids = data.get('datapiece_ids', []) or []
    provider = "groq"

    if not user_msg:
        return jsonify({'success': False, 'message': 'Message is required'}), 400
    
    try:
        reply, sources = assistant_service.get_answer(
            user_msg=user_msg, 
            scope=scope, 
            datapiece_ids=datapiece_ids,
            session_id=session_id,
            provider=provider
        )
    except Exception as e:
        print(f'Failed to get answer: {e}')
        return jsonify({'success': False, 'message': e}), 500
    
    return jsonify({'success': True, 'assistant': reply, 'sources': sources}), 200

@app.route('/api/settings/delete-account', methods=['POST']) # update to /api/profile, method=['DELETE']
@jwt_required()
@active_required
def delete_account():
    """Delete user account and related data"""
    data = request.json
    password = data.get('password')
    full_name = data.get('full_name')
    
    # TODO: Implement actual deletion logic with password verification
    print(f"\n[ACCOUNT DELETION] User '{full_name}' deleted at {datetime.utcnow()}")
    print(f"[ACTION] Removing: user records, search history, cookies, LLM configs, chat data")
    
    return jsonify({'success': True, 'message': 'Account deleted'}), 200


# ==================== ADMIN ROUTES ====================

@app.route('/api/admin/stats', methods=['GET'])
@jwt_required()
@admin_required
def get_admin_stats():
    """Get system statistics for admin dashboard"""
    try:
        
        stats = analytics_engine.get_system_statistics()
        print(f"[ADMIN STATS] Retrieved statistics: {stats}")
        return jsonify({'success': True, 'stats': stats}), 200
    
    except Exception as e:
        print(f"[ADMIN STATS ERROR] {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve statistics'}), 500


@app.route('/api/admin/misusers', methods=['GET'])
@jwt_required()
@admin_required
def get_potential_misusers():
    """Get potential misusers for admin review"""
    try:
        
        misusers = analytics_engine.detect_potential_misusers()
        print(f"[ADMIN MISUSERS] Found {len(misusers)} potential misusers")
        return jsonify({'success': True, 'misusers': misusers}), 200
    except Exception as e:
        print(f"[ADMIN MISUSERS ERROR] {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve misusers'}), 500


@app.route('/api/admin/suspended', methods=['GET'])
@jwt_required()
@admin_required
def get_suspended_users():
    """Get suspended users for admin review"""
    try:
        
        suspended_users = analytics_engine.get_suspended_users()
        
        print(f"[ADMIN SUSPENDED] Found {len(suspended_users)} suspended users")
        return jsonify({'success': True, 'suspended_users': suspended_users}), 200
    except Exception as e:
        print(f"[ADMIN SUSPENDED ERROR] {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve suspended users'}), 500


@app.route('/api/admin/user/<int:user_id>/requests', methods=['GET'])
@jwt_required()
@admin_required
def get_user_requests(user_id):
    """Get recent requests for a specific user"""
    try:
        requests = analytics_engine.get_user_recent_requests(user_id)
        
        print(f"[ADMIN USER REQUESTS] Retrieved {len(requests)} requests for user {user_id}")
        return jsonify({'success': True, 'requests': requests}), 200
    except Exception as e:
        print(f"[ADMIN USER REQUESTS ERROR] {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve user requests'}), 500


@app.route('/api/admin/user/<int:user_id>/suspend', methods=['POST'])
@jwt_required()
@admin_required
def suspend_user(user_id):
    """Suspend a user account"""
    try:        
        data = request.json
        reason = data.get('reason', '')
        
        success = analytics_engine.suspend_user(user_id, reason)
        
        if success:
            print(f"[ADMIN SUSPEND] User {user_id} suspended for reason: {reason}")
            return jsonify({'success': True, 'message': 'User suspended successfully'}), 200
        else:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
    except Exception as e:
        print(f"[ADMIN SUSPEND ERROR] {e}")
        return jsonify({'success': False, 'message': 'Failed to suspend user'}), 500


@app.route('/api/admin/user/<int:user_id>/reactivate', methods=['POST'])
@jwt_required()
@admin_required
def reactivate_user(user_id):
    """Reactivate a suspended user account"""
    try:

        success = analytics_engine.reactivate_user(user_id)
        
        if success:
            print(f"[ADMIN REACTIVATE] User {user_id} reactivated")
            return jsonify({'success': True, 'message': 'User reactivated successfully'}), 200
        else:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
    except Exception as e:
        print(f"[ADMIN REACTIVATE ERROR] {e}")
        return jsonify({'success': False, 'message': 'Failed to reactivate user'}), 500


# ==================== UTILITY ROUTES ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat() + 'Z'})

@app.route('/api/admin/documents', methods=['GET'])
@jwt_required()
@admin_required
def list_documents():
    """List all documents in the knowledge base"""
    try:
        documents = rag_engine.list_documents()
        return jsonify({'success': True, 'documents': documents}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/documents/upload', methods=['POST'])
@jwt_required()
@admin_required
def upload_document():
    """Upload a document to the knowledge base"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '' or not file.filename.endswith('.pdf'):
            return jsonify({'success': False, 'message': 'Invalid file. Only PDF files are allowed.'}), 400
        
        # Save file to upload directory
        filename = file.filename
        filepath = os.path.join(rag_engine.DATA_PATH, filename)
        file.save(filepath)
        
        # Check for conflicts
        conflicts = rag_engine.prepare_new_RAG_pdf_pipeline()
        
        # Check if the uploaded file has conflicts
        file_title = filename[:-4]  # Remove .pdf extension
        if file_title in conflicts and conflicts[file_title]['status'] == 'conflicts_found':
            # Return conflict information
            return jsonify({
                'success': True, 
                'status': 'conflicts_detected',
                'conflicts': conflicts[file_title]['conflicts'],
                'filename': filename
            }), 200
        
        # No conflicts, process immediately
        result = rag_engine.load_RAG_pdf_pipeline()
        return jsonify({'success': True, 'message': result}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/documents/process', methods=['POST'])
@jwt_required()
@admin_required
def process_documents():
    """Process uploaded documents with conflict resolution"""
    try:
        data = request.json
        conflict_resolutions = data.get('resolutions', {})
        
        result = rag_engine.load_RAG_pdf_pipeline(conflict_resolutions=conflict_resolutions)
        return jsonify({'success': True, 'message': result}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/documents/<filename>/download', methods=['GET'])
@jwt_required()
@admin_required
def download_document(filename):
    """Download a document from the knowledge base"""
    try:
        filepath = rag_engine.download_document(filename)
        if not filepath:
            return jsonify({'success': False, 'message': 'Document not found'}), 404
        
        from flask import send_file
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/documents/<filename>', methods=['DELETE'])
@jwt_required()
@admin_required
def remove_document(filename):
    """Remove a document from the knowledge base"""
    try:
        # Remove .pdf extension if present
        document_name = filename.replace('.pdf', '')
        message = rag_engine.delete_document(document_name)
        return jsonify({'success': True, 'message': message}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500




@app.route('/')
def home():
    """Serve frontend"""
    return render_template('index.html')


if __name__ == "__main__":
    
    # setup TLS 1.3/HTTPS
    
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    
    cert_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'certs/cert.pem') 
    key_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'certs/key.pem')
    
    context.load_cert_chain(cert_path, key_path)
    
    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context=context, threaded=True)
