import os
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time

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
        """Lightweight verification: try to access mobile Facebook with provided cookies_map.
        cookies_map is expected to be {'c_user': '...', 'xs': '...', ...}
        Returns True if cookies appear valid (not redirected to login, user account in place), False otherwise.
        """
        if not cookies_map:
            return False
        
        # Minimal checks
        if 'c_user' not in cookies_map or 'xs' not in cookies_map:
            print("[FB COOKIE VERIFY] Missing c_user/xs in cookies map.")
            return False

        try:
            r = requests.get('https://m.facebook.com/', cookies=cookies_map, timeout=6)
            if r.status_code != 200:
                print("[FB COOKIE VERIFY] Non-200 status code:", r.status_code)
                return False
            url_lower = r.url.lower() if r.url else ''
            text_lower = (r.text or '').lower()
            if 'login' in url_lower:
                print("[FB COOKIE VERIFY] Redirected to login page.", url_lower, "<>", text_lower)
                return False
            if not "profile.php" in text_lower or not "logout" in text_lower:
                print("[FB COOKIE VERIFY] Profile/home not reachable (not logged in)")
                return False
            
            return True
        
        except Exception as e:
            print(f"[FB COOKIE VERIFY] request failed: {e}")
            return False
        
@staticmethod
def login_with_credentials(login: str, password: str, headless: bool = True, wait_seconds: int = 10) -> dict:
    """Attempt to log into Facebook using Selenium and return cookie map {name: value}.
    Note: This may fail on accounts with 2FA or checkpoint flows.
    """
    options = Options()
    if headless:
        options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        # Use mobile login which is often simpler
        driver.get('https://m.facebook.com/login.php')
        time.sleep(1.2)

        # Find fields
        try:
            email_el = driver.find_element(By.NAME, 'email')
            pass_el = driver.find_element(By.NAME, 'pass')
        except Exception:
            # Try desktop login form
            email_el = driver.find_element(By.ID, 'email')
            pass_el = driver.find_element(By.ID, 'pass')

        email_el.clear()
        email_el.send_keys(login)
        pass_el.clear()
        pass_el.send_keys(password)

        # submit
        try:
            login_btn = driver.find_element(By.NAME, 'login')
            login_btn.click()
        except Exception:
            pass

        # Wait a bit for redirect
        time.sleep(wait_seconds)

        # Check if we are logged in by presence of c_user cookie
        cookies = driver.get_cookies()
        cookie_map = {c['name']: c['value'] for c in cookies}

        # Basic validation
        if 'c_user' in cookie_map and 'xs' in cookie_map:
            return cookie_map
        else:
            # could be checkpoint/2FA — return what we have but caller should verify
            return cookie_map
    finally:
        try:
            driver.quit()
        except Exception:
            pass



    
# EXAMPLE cookies:
"""
{"c_user":"100023014805164",
    "xs":"22%3A4XJeCa-x5wim4Q%3A2%3A1749653584%3A-1%3A-1%3A%3AAcUXpVYZcsxTBRE36-lFVO2lXisFfm33AieqFjGahCE",
    "datr": "NJhJaIAAgvnb3W5fqWTbQ3Eu",
    "fr": "1vq973m9m09UI7hHr.AWchAR9j2aQPhYs5ue08n6bqP7Oiyt9X6CC56KYkIQGB6_6pYc8.Bo0t8U..AAA.0.0.BpHuTw.AWeCBdNi_z_qik3A1ebQbLViFTU", # not needed
    "sb": "6-0mZidilwynboWT049OrT-u"
    }
"""