from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import bcrypt
import json


from config import Config
from models import db, User, Report, SearchHistory

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    jwt = JWTManager(app)
    CORS(app)
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app

app = create_app()

# Helper functions
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

# API Routes
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        
        # Validation
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required.'}), 400
        
        if len(password) < 8:
            return jsonify({'success': False, 'message': 'Password must be at least 8 characters long.'}), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'success': False, 'message': 'Email already registered.'}), 400
        
        # Create new user
        password_hash = hash_password(password)
        new_user = User(
            email=email,
            password_hash=password_hash,
            name=name,
            confirmed=False  # Email confirmation required
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # In real app: send confirmation email here
        return jsonify({
            'success': True, 
            'message': 'Registration successful. Please check your email for confirmation instructions.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Registration failed. Please try again.'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required.'}), 400
        
        # Find user
        user = User.query.filter_by(email=email).first()
        if not user or not verify_password(password, user.password_hash):
            return jsonify({'success': False, 'message': 'Invalid email or password.'}), 401
        
        if not user.confirmed:
            return jsonify({'success': False, 'message': 'Please confirm your email before logging in.'}), 403
        
        # Create access token
        access_token = create_access_token(identity=email)
        
        print(access_token)
        
        return jsonify({
            'success': True,
            'message': 'Login successful.',
            'access_token': access_token,
            'user': {
                'email': user.email,
                'name': user.name
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': 'Login failed. Please try again.'}), 500


@app.route('/api/search', methods=['POST'])
@jwt_required()
def search():
    try:
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found.'}), 404
        
        data = request.json
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'success': False, 'message': 'Search query is required.'}), 400
        
        # Generate mock report (in real app: trigger actual scraping/analysis)
        report_data = generate_mock_report(query, current_user_email)
        
        # Save report to database
        new_report = Report(
            report_id=report_data['report_id'],
            user_id=user.id,
            query=query,
            status='completed',
            executive_summary=report_data['executive_summary'],
            risk_distribution=json.dumps(report_data['risk_distribution']),
            detailed_findings=json.dumps(report_data['detailed_findings']),
            recommendations=json.dumps(report_data['recommendations']),
            source_distribution=json.dumps(report_data['source_distribution'])
        )
        
        db.session.add(new_report)
        
        # Add to search history
        search_history = SearchHistory(
            user_id=user.id,
            query=query,
            report_id=report_data['report_id']
        )
        
        db.session.add(search_history)
        db.session.commit()
        
        return jsonify({'success': True, 'report': report_data})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Search failed. Please try again.'}), 500

# Entry point of frontend serve
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
