import bcrypt
from flask_jwt_extended import create_access_token
from models import User


class AuthService:
    """Service for handling user authentication operations"""
    
    def __init__(self, db):
        self.db = db
    
    def register_user(self, email, password, name):
        """
        Register a new user
        
        Args:
            email: User's email address
            password: User's password (plain text)
            name: User's full name
            
        Returns:
            dict: Success response with message
            
        Raises:
            ValueError: If validation fails or email already exists
        """
        email = email.strip().lower()
        name = name.strip()
        
        # Validation
        if not email or not password:
            raise ValueError('Email and password are required.')
        
        if len(password) < 8:
            raise ValueError('Password must be at least 8 characters long.')
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            raise ValueError('Email already registered.')
        
        # Create new user
        password_hash = self._hash_password(password)
        new_user = User(
            email=email,
            password_hash=password_hash,
            name=name,
            confirmed=False
        )
        
        self.db.session.add(new_user)
        self.db.session.commit()
        
        return {
            'success': True,
            'message': 'Registration successful. Please check your email for confirmation instructions.'
        }
    
    def login_user(self, email, password):
        """
        Authenticate user and create access token
        
        Args:
            email: User's email address
            password: User's password (plain text)
            
        Returns:
            dict: Success response with access token and user info
            
        Raises:
            ValueError: If credentials are invalid or email not confirmed
        """
        email = email.strip().lower()
        
        if not email or not password:
            raise ValueError('Email and password are required.')
        
        # Find user
        user = User.query.filter_by(email=email).first()
        
        if not user or not self._verify_password(password, user.password_hash):
            raise ValueError('Invalid email or password.')
        
        if not user.confirmed:
            raise ValueError('Please confirm your email before logging in.')
        
        # Create access token
        access_token = create_access_token(identity=email)
        
        return {
            'success': True,
            'message': 'Login successful.',
            'access_token': access_token,
            'user': {
                'email': user.email,
                'name': user.name
            }
        }
    
    def confirm_email(self, email):
        """
        Confirm user's email address
        
        Args:
            email: User's email address
            
        Returns:
            dict: Success response
            
        Raises:
            ValueError: If user not found
        """
        email = email.strip().lower()
        
        user = User.query.filter_by(email=email).first()
        if not user:
            raise ValueError('User not found.')
        
        user.confirmed = True
        self.db.session.commit()
        
        return {
            'success': True,
            'message': 'Email confirmed successfully. You can now log in.'
        }
    
    def change_password(self, email, current_password, new_password):
        """
        Change user's password
        
        Args:
            email: User's email address
            current_password: Current password for verification
            new_password: New password to set
            
        Returns:
            dict: Success response
            
        Raises:
            ValueError: If validation fails or current password incorrect
        """
        if not current_password or not new_password:
            raise ValueError('Current and new passwords are required.')
        
        if len(new_password) < 8:
            raise ValueError('New password must be at least 8 characters long.')
        
        user = User.query.filter_by(email=email).first()
        if not user:
            raise ValueError('User not found.')
        
        # Verify old password
        if not user.password_hash or not self._verify_password(current_password, user.password_hash):
            raise ValueError('Current password is incorrect.')
        
        # Update password
        user.password_hash = self._hash_password(new_password)
        self.db.session.commit()
        
        return {
            'success': True,
            'message': 'Password changed successfully.'
        }
    
    def _hash_password(self, password):
        """Hash a password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def _verify_password(self, password, password_hash):
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
