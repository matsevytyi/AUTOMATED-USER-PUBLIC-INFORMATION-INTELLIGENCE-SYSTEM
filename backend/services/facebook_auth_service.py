import json
from datetime import datetime
from dateutil.relativedelta import relativedelta

from models import User, FacebookCookies
from backend.utils.facebook_cookie_manager import FacebookCookieManager


class FacebookAuthService:
    """Service for managing Facebook authentication and cookies"""
    
    def __init__(self, db):
        self.db = db
    
    def save_cookies(self, user_email, cookies_json):
        """
        Save Facebook cookies for a user after validation
        
        Args:
            user_email: Email of the user
            cookies_json: JSON string containing Facebook cookies
            
        Returns:
            dict: Success response
            
        Raises:
            ValueError: If cookies are invalid or validation fails
        """
        # Parse cookies
        try:
            cookies = json.loads(cookies_json)
            if not all(k in cookies for k in ['c_user', 'xs']):
                raise ValueError('Invalid cookies format or missing c_user/xs')
        except json.JSONDecodeError:
            raise ValueError('Invalid JSON format')
        
        # Verify cookies are valid
        try:
            is_valid = FacebookCookieManager.verify_cookies_map(cookies)
        except Exception:
            is_valid = False
        
        if not is_valid:
            raise ValueError('Provided cookies appear invalid or not authenticated.')
        
        # Save to database
        expires_at = datetime.utcnow() + relativedelta(months=1)
        
        fc = FacebookCookies.query.filter_by(user_email=user_email).first()
        if not fc:
            fc = FacebookCookies(
                user_email=user_email,
                cookies_json=json.dumps(cookies),
                saved_at=datetime.utcnow(),
                expires_at=expires_at
            )
            self.db.session.add(fc)
        else:
            fc.cookies_json = json.dumps(cookies)
            fc.saved_at = datetime.utcnow()
            fc.expires_at = expires_at
        
        self.db.session.commit()
        
        return {'success': True, 'message': 'Cookies saved successfully.'}
    
    def login_with_credentials(self, user_email, fb_login, fb_password, headless=True):
        """
        Login to Facebook using credentials and save extracted cookies
        
        Args:
            user_email: Email of the user in our system
            fb_login: Facebook login/email
            fb_password: Facebook password
            headless: Whether to run browser in headless mode
            
        Returns:
            dict: Success response with message
            
        Raises:
            ValueError: If login fails or credentials are invalid
        """
        if not fb_login or not fb_password:
            raise ValueError('Login and password are required.')
        
        # Attempt login using FacebookCookieManager
        try:
            cookie_map = FacebookCookieManager.login_with_credentials(
                fb_login,
                fb_password,
                headless=bool(headless)
            )
        except Exception as e:
            raise ValueError(f'Failed to perform login: {str(e)}')
        
        # Validate extracted cookies
        try:
            is_valid = FacebookCookieManager.verify_cookies_map(cookie_map)
        except Exception:
            is_valid = False
        
        if not is_valid:
            raise ValueError('Login succeeded but cookies appear invalid or 2FA required.')
        
        # Save cookies to database
        expires_at = datetime.utcnow() + relativedelta(months=1)
        
        fc = FacebookCookies.query.filter_by(user_email=user_email).first()
        if not fc:
            fc = FacebookCookies(
                user_email=user_email,
                cookies_json=json.dumps(cookie_map),
                saved_at=datetime.utcnow(),
                expires_at=expires_at
            )
            self.db.session.add(fc)
        else:
            fc.cookies_json = json.dumps(cookie_map)
            fc.saved_at = datetime.utcnow()
            fc.expires_at = expires_at
        
        self.db.session.commit()
        
        return {'success': True, 'message': 'Logged in and cookies saved.'}
    
    def get_cookies(self, user_email):
        """
        Get Facebook cookies for a user (validated)
        
        Args:
            user_email: Email of the user
            
        Returns:
            dict or None: Cookie map if valid, None otherwise
        """
        fc = FacebookCookies.query.filter_by(user_email=user_email).first()
        
        if not fc or not fc.cookies_json:
            return None
        
        try:
            cookies = json.loads(fc.cookies_json)
            # Verify cookies are still valid
            if FacebookCookieManager.verify_cookies_map(cookies):
                return cookies
        except Exception:
            pass
        
        return None
    
    def delete_cookies(self, user_email):
        """
        Delete Facebook cookies for a user
        
        Args:
            user_email: Email of the user
            
        Returns:
            dict: Success response
        """
        fc = FacebookCookies.query.filter_by(user_email=user_email).first()
        
        if fc:
            self.db.session.delete(fc)
            self.db.session.commit()
        
        return {'success': True, 'message': 'Cookies deleted successfully.'}
