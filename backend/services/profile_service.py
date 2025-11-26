from models import User


class ProfileService:
    """Service for managing user profile and settings"""
    
    def __init__(self, db):
        self.db = db
    
    def get_profile(self, user_email):
        """
        Get user profile information
        
        Args:
            user_email: Email of the user
            
        Returns:
            dict: User profile data
            
        Raises:
            ValueError: If user not found
        """
        user = User.query.filter_by(email=user_email).first()
        
        if not user:
            raise ValueError('User not found.')
        
        return {
            'email': user.email,
            'name': user.name,
            'confirmed': user.confirmed,
            'created_at': user.created_at.isoformat() + 'Z',
            'total_reports': len(user.reports),
            'total_searches': len(user.searches),
            'theme': getattr(user, 'theme', None)
        }
    
    def set_theme(self, user_email, theme):
        """
        Set user theme preference
        
        Args:
            user_email: Email of the user
            theme: Theme name ('light', 'dark', 'device')
            
        Returns:
            dict: Success response with theme
            
        Raises:
            ValueError: If user not found or theme invalid
        """
        if theme not in ['light', 'dark', 'device']:
            raise ValueError('Invalid theme. Must be light, dark, or device.')
        
        user = User.query.filter_by(email=user_email).first()
        if not user:
            raise ValueError('User not found.')
        
        user.theme = theme
        self.db.session.commit()
        
        return {'success': True, 'theme': theme}
