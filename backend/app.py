from flask import Flask, render_template
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import bcrypt


from config import Config
from models import db

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


# Entry point of frontend serve
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
