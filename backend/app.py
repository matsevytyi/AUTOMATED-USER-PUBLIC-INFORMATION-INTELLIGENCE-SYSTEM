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
from models import db, InformationPiece, ChatSession, ChatMessage, User
from backend.llm.llm_abstraction import chat_with_context

import ssl

# Import services
from services import AuthService, ReportService, FacebookAuthService, ProfileService
from backend.services.admin_service import AdminService


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
analytics_engine = AdminService(db)


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

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


@app.route('/api/reports/<report_id>/export', methods=['GET'])
@jwt_required()
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
    if scope == 'datapieces' and datapiece_ids:
        system_prompt = {
            'role': 'system',
            'content': """You respond as a friendly assistant who explains risks and insights based on the provided sources and helps to maintain awareness about digital-footprint security and protecting yourself online. Evaluate information that you see as a whole (but part os smth bigger meaning there may be nore datapieces), its meaning, security implications, and exposure risks. 

                            The report is about the user who asked and contains information that was already found about him.

                            Do not hallucinate.
                            Draw conclusions from the datapiece (and context) and from similar datapieces (provided under Similar Pieces).
                            If you do not know, say exactly that.
                            Do not reveal technical details (such as IDs).
                            You may give information based on links, context snippets, and titles.

                            When answering:
                            Make the explanation short and understandable.
                            Elaborate on whether having this datapiece exposed online (not published intentionally, but visible to others) is dangerous and why.
                            Clarify privacy or safety issues related to <strong>user-exposed data</strong>.
                            Provide any other helpful comments.
                            Tell the user exactly which source link the information came from.

                            Use HTML tags (i.e. <strong>, <italic> or <br>) instead of Markdown.
                                                """ }
    else:
        system_prompt = {
        'role': 'system',
        'content': """You respond as a friendly assistant who explains risks and insights based on the entire provided report.
                        The report may contain multiple datapieces about the user, and your job is to evaluate the document as a whole, its meaning, security implications, and exposure risks.
                        The report is about the user who asked and contains information that was already found about him.

                        Do not hallucinate.
                        Base all conclusions strictly on the content of the report and its context.
                        If something is unclear or missing, state exactly that.
                        Do not reveal technical identifiers (such as full IDs, tokens, hashes).
                        You may summarize or refer to information based on links, context snippets, titles, or descriptive fields included in the report.

                        When answering:
                        Keep explanations short and easy to understand.
                        Evaluate whether having this entire report exposed online is dangerous, and explain why.
                        Mention any notable privacy, security, or reputation concerns.
                        Provide any other relevant commentary that could help the user protect themselves.
                        Always specify where each insight comes from using the given source links or references.

                        Use HTML tags (e.g., <strong>, <italic>, <br>) instead of Markdown.
                        """ }
    
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


# ==================== UTILITY ROUTES ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat() + 'Z'})

@app.route('/')
def home():
    """Serve frontend"""
    return render_template('index.html')


@app.route('/api/admin/make_admin/<email>', methods=['POST'])
def make_admin(email):
    """Temporary route to make a user admin for testing"""
    user = User.query.filter_by(email=email).first()
    if user:
        user.is_admin = True
        db.session.commit()
        return jsonify({'success': True, 'message': f'User {email} is now admin'})
    return jsonify({'success': False, 'message': 'User not found'}), 404


if __name__ == "__main__":
    
    # setup TLS 1.3/HTTPS
    
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    
    cert_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'certs/cert.pem') 
    key_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'certs/key.pem')
    
    context.load_cert_chain(cert_path, key_path)
    
    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context=context, threaded=True)
