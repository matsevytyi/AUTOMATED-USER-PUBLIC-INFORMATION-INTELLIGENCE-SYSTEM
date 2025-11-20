import os
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta

COOKIES_DIR = 'backend/data_collection/facebook'
os.makedirs(COOKIES_DIR, exist_ok=True)

class FacebookCookieManager:
    """Manages Facebook cookies per session"""
    
    @staticmethod
    def get_cookies_path(user_id: str) -> str:
        return os.path.join(COOKIES_DIR, f'cookies_{user_id}.json')
    
    @staticmethod
    def save_cookies(user_id: str, cookies: dict) -> bool:
        """Save cookies with expiration metadata"""
        try:
            
            expires_at = datetime.utcnow() + relativedelta(months=1)
            expires_at_iso = expires_at.isoformat()
            
            data = {
                'cookies': cookies,
                'saved_at': datetime.utcnow().isoformat(),
                'expires_at': expires_at_iso  # Will be updated on expiration detection
            }
            path = FacebookCookieManager.get_cookies_path(user_id)
            with open(path, 'w') as f:
                json.dump(data, f)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save cookies: {str(e)}")
            return False
    
    @staticmethod
    def load_cookies(user_id: str) -> dict:
        """Load cookies for user"""
        path = FacebookCookieManager.get_cookies_path(user_id)
        if not os.path.exists(path):
            return {}
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                return data.get('cookies', {})
        except:
            return {}
    
    @staticmethod
    def is_expired(user_id: str) -> bool:
        """Check if cookies are marked as expired"""
        path = FacebookCookieManager.get_cookies_path(user_id)
        if not os.path.exists(path):
            return True
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                return data.get('expires_at') is not None
        except:
            return True

    @staticmethod
    def verify_cookies_map(cookies_map: dict) -> bool:

        return True

# EXAMPLE cookies:
"""
{"c_user":"100023014805164",
    "xs":"22%3A4XJeCa-x5wim4Q%3A2%3A1749653584%3A-1%3A-1%3A%3AAcUXpVYZcsxTBRE36-lFVO2lXisFfm33AieqFjGahCE",
    "datr": "NJhJaIAAgvnb3W5fqWTbQ3Eu",
    "fr": "1vq973m9m09UI7hHr.AWchAR9j2aQPhYs5ue08n6bqP7Oiyt9X6CC56KYkIQGB6_6pYc8.Bo0t8U..AAA.0.0.BpHuTw.AWeCBdNi_z_qik3A1ebQbLViFTU",
    "sb": "6-0mZidilwynboWT049OrT-u"
    }
"""