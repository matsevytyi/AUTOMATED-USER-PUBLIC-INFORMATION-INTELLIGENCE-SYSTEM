from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from queue import Queue

import time
import random
import json
import os
import sys

# Standardize path imports
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

class FacebookScrapingService:
    
    def __init__(self, remote_url=None, headless=True):
        """
        :param remote_url: URL of the Selenium Grid (e.g., 'http://selenium-chrome:4444/wd/hub')
                           If None, it tries to read env var 'SELENIUM_REMOTE_URL'.
                           If still None, it falls back to Local ChromeDriver.
        :param headless: Run without UI (ignored if running Remote, as Remote is always headless)
        """
       
        remote_url = "http://localhost:4444/wd/hub"
        self.remote_url = remote_url or os.getenv('SELENIUM_REMOTE_URL')  # Execution Mode (Docker main and Local is fallback)
        self.headless = headless
        
        self.cookies = []
        self.scraper = self._prepare_scraper()
        
    # ================== PUBLIC WRAPPERS ==================
            
    # multithreading wrappers
    def search_request_background(self, search_request, results: Queue, cookies):
        print(f"[{'REMOTE' if self.remote_url else 'LOCAL'}] Scraping Facebook search results...")
        if isinstance(cookies, str):
            self.cookies = self._load_cookies_from_json(cookies)
        else:
            self.cookies = self._load_cookies_from_object(cookies)
            
        try:
            facebook_data = self.search_request(query=search_request, amount_of_posts=100)
            results.put(facebook_data)
        except Exception as e:
            print(f"Error in search thread: {e}")

    def search_and_scrape_profiles_background(self, search_request, results: Queue, cookies, profiles_max=10):
        print(f"[{'REMOTE' if self.remote_url else 'LOCAL'}] Obtaining Facebook profiles...")
        
        if isinstance(cookies, str):
            self.cookies = self._load_cookies_from_json(cookies)
        else:
            self.cookies = self._load_cookies_from_object(cookies)
            
        try:
            user_profiles = self.obtain_profiles(search_request)
            user_profiles = user_profiles[:profiles_max]
            for profile in user_profiles:
                print("Scraping Facebook profile:", profile)
                profile_data = self.search_profile(profile, amount_of_posts=100)
                results.put(profile_data)
        except Exception as e:
            print(f"Error in profile thread: {e}")
    
    # simple sequential wrappers        
    def search_profile(self, profile_url, amount_of_posts=50, human=True):
        return self._scrape_page(url=profile_url, amount_of_posts=amount_of_posts, human=human)

    def search_request(self, query, amount_of_posts=50, human=True):
        url = f"https://www.facebook.com/search/posts/?q={query}"
        return self._scrape_page(url=url, amount_of_posts=amount_of_posts, human=human)
    
    def obtain_profiles(self, user_name_surname):
        url = f"https://www.facebook.com/search/people/?q={user_name_surname}"
        self._apply_cookies(url)
        
        # Scroll once to ensure lazy loading triggers
        self.scraper.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        soup = BeautifulSoup(self.scraper.page_source, 'html.parser')
        links = []
        for a_tag in soup.find_all("a", href=True):
            links.append(a_tag['href'])
        
        profile_links = self._extract_and_filter_profiles(links)
        return list(set(profile_links))
    
    # utils
    def close(self):
        try:
            self.scraper.quit()
        except:
            pass

    # ================== PRIVATE METHODS ==================
    def _prepare_scraper(self):
        options = Options()
        
        # --- CRITICAL DOCKER OPTIONS ---
        options.add_argument('--no-sandbox') 
        options.add_argument('--disable-dev-shm-usage') # Prevents crashing in Docker containers
        options.add_argument("--disable-notifications")
        options.add_argument("--start-maximized")

        if self.headless:
            options.add_argument('--headless=new')

        # --- HYBRID CONNECTION LOGIC ---
        if self.remote_url:
            print(f"Connecting to Remote Selenium at: {self.remote_url}")
            try:
                driver = webdriver.Remote(
                    command_executor=self.remote_url,
                    options=options
                )
                return driver
            except Exception as e:
                print(f"CRITICAL: Could not connect to Docker Selenium at {self.remote_url}. Error: {e}")
                raise e
        else:
            print("Using Local ChromeDriver (Fallback)")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            return driver

    def _load_cookies_from_json(self, cookies_path):
        if not os.path.isabs(cookies_path):
            cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), cookies_path)
            
        with open(cookies_path, "r") as file:
            try:
                return json.load(file)
            except Exception:
                raise Exception(f"Failed to load cookies from {cookies_path}")
    
    def _load_cookies_from_object(self, cookies):
        if not cookies:
            return []
        if isinstance(cookies, list):
            return cookies
        elif isinstance(cookies, dict):
            formatted_cookies = []
            for name, value in cookies.items():
                formatted_cookies.append({
                    'name': name,
                    'value': value,
                    'domain': '.facebook.com',
                    'path': '/'
                })
            return formatted_cookies
        return []
        
    def _extract_and_filter_profiles(self, links_soup):
        profile_links = []
        for href in links_soup:
            if "facebook.com/profile.php?id=" in href:
                profile_links.append(href)
            elif (
                "facebook.com/" in href
                and "facebook.com/groups/" not in href
                and "facebook.com/control_panel/" not in href
                and "facebook.com/reel" not in href
                and "facebook.com/notifications" not in href
                and "facebook.com/pages/" not in href
                and "?notif_id=" not in href
                and "/posts/" not in href
                and "ref=notif" not in href
            ):
                profile_links.append(href)
        return list(set(profile_links))

    def _apply_cookies(self, target_url):
        print(f"Applying cookies and navigating to: {target_url}")
        
        # 1. Go to a neutral valid page on the domain first.
        # This lets us set cookies without triggering a "Login Required" redirect loop.
        try:
            self.scraper.get("https://www.facebook.com/robots.txt")
        except Exception:
            pass

        # 2. Add Cookies
        if self.cookies:
            for cookie in self.cookies:
                try:
                    # Clean up cookie fields that cause Selenium errors
                    if 'expiry' in cookie: del cookie['expiry']
                    if 'sameSite' in cookie: del cookie['sameSite']
                    
                    self.scraper.add_cookie(cookie)
                except Exception:
                    pass
        else:
            print("WARNING: No cookies available!")

        # 3. NOW navigate to the actual target
        self.scraper.get(target_url)
        time.sleep(3)
        
        # 4. Check if we are stuck on a login page
        if "login" in self.scraper.current_url or "privacy/consent" in self.scraper.current_url:
            print("[CRITICAL] Redirected to Login/Consent page. Cookies might be invalid or expired.")
            # Optional: Check for consent button here if needed
            try:
                btns = self.scraper.find_elements(By.XPATH, "//span[contains(text(), 'Allow')] | //span[contains(text(), 'Decline')]")
                if btns:
                    btns[0].click()
                    time.sleep(2)
            except:
                pass

    def _scrape_page(self, url, amount_of_posts=50, human=True):
        self._apply_cookies(url)
        
        # TODO: detect if page is bad (e.g. cookie confirmation) and what to do
        
        # Use a Set to store unique posts (prevents duplicates)
        collected_posts = set()
        
        print(f"Page Title: {self.scraper.title}")
        
        # Selectors to try (in order of preference)
        post_selectors = [
            'div[data-ad-rendering-role="story_message"]',
            'div[data-ad-preview="message"]',
            'div[role="article"] div[dir="auto"]' # Generic text container in a post
        ]
        
        last_height = self.scraper.execute_script("return document.body.scrollHeight")
        
        consecutive_scroll_fails = 0
        
        while len(collected_posts) < amount_of_posts:
            # 1. SCRAPE CURRENT VIEWPORT
            soup = BeautifulSoup(self.scraper.page_source, 'html.parser')
            
            found_new_data = False
            for selector in post_selectors:
                elements = soup.select(selector)
                if elements:
                    for el in elements:
                        text = el.get_text(strip=True)
                        if len(text) > 10 and text not in collected_posts: # Filter short noise
                            collected_posts.add(text)
                            found_new_data = True
                    # If we found data with this selector, stop trying others for this iteration
                    if found_new_data:
                        break
            
            print(f"Collected: {len(collected_posts)} / {amount_of_posts}")
            
            if len(collected_posts) >= amount_of_posts:
                break

            # 2. SCROLL DOWN
            pause = random.uniform(2.0, 3.5) if human else 1.5
            self.scraper.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)

            # 3. CHECK IF NEW CONTENT LOADED
            new_height = self.scraper.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                consecutive_scroll_fails += 1
                print(f"  - No new content loaded (Attempt {consecutive_scroll_fails}/2)")
                
                # Try jiggling the scroll to trigger lazy loading
                self.scraper.execute_script("window.scrollBy(0, -300);")
                time.sleep(1)
                self.scraper.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                new_height = self.scraper.execute_script("return document.body.scrollHeight")
                
                if new_height == last_height and consecutive_scroll_fails >=2:
                    print("Reached end of feed or blocked.")
                    break
            else:
                consecutive_scroll_fails = 0
                last_height = new_height

        # Convert set back to list
        return list(collected_posts)
    
if __name__ == '__main__':
    # Usage Example:
    # 1. To use LOCAL: Run as normal
    # 2. To use DOCKER: export SELENIUM_REMOTE_URL='http://localhost:4444/wd/hub' && python script.py
    
    fb = FacebookScrapingService(headless=False)
    try:
        # Pass a mock dict or load real cookies
        fb.search_request("Python Programming")
        print("Service initialized successfully")
    finally:
        fb.close()
        
        
## try next
# def _scrape_page(self, url, amount_of_posts=50, human=True):
#         self._apply_cookies(url)
        
#         # Use a Dictionary to store unique posts: { text_content: link_url }
#         # This prevents duplicates while keeping the link associated with the text
#         collected_data = {}
        
#         print(f"Page Title: {self.scraper.title}")
        
#         consecutive_scroll_fails = 0
#         last_height = self.scraper.execute_script("return document.body.scrollHeight")
        
#         while len(collected_data) < amount_of_posts:
#             # 1. SCRAPE CURRENT VIEWPORT
#             soup = BeautifulSoup(self.scraper.page_source, 'html.parser')
            
#             # We target the main article container to keep text and link together
#             # 'div[role="article"]' is the standard container for a Feed Post
#             posts = soup.find_all("div", role="article")
            
#             found_new_data = False
            
#             for post in posts:
#                 # A. Extract Text
#                 # We look for the main text div (dir="auto") inside the article
#                 text_div = post.find("div", dir="auto")
#                 text = text_div.get_text(strip=True) if text_div else post.get_text(strip=True)
                
#                 # Filter noise (short text like "Suggested for you" or empty)
#                 if len(text) < 15:
#                     continue
                
#                 # B. Extract Link
#                 post_link = url # Default to the profile/search URL (Fallback)
                
#                 # Try to find the specific permalink
#                 # Logic: The timestamp is usually an anchor tag that links to the post
#                 # We look for all links in the post and pick the one that looks like a permalink
#                 try:
#                     links = post.find_all("a", href=True)
#                     for a in links:
#                         href = a['href']
#                         # Common patterns for Facebook permalinks
#                         if "/posts/" in href or "/videos/" in href or "/photo" in href or "fbid=" in href:
#                             # Clean up the URL (remove tracking parameters)
#                             if "facebook.com" not in href:
#                                 post_link = "https://www.facebook.com" + href
#                             else:
#                                 post_link = href
                            
#                             # Stop after finding the first likely permalink
#                             break
#                 except Exception:
#                     pass

#                 # C. Store (Deduplicate based on text)
#                 if text not in collected_data:
#                     collected_data[text] = post_link
#                     found_new_data = True

#             print(f"Collected: {len(collected_data)} / {amount_of_posts}")
            
#             if len(collected_data) >= amount_of_posts:
#                 break

#             # 2. SCROLL DOWN
#             pause = random.uniform(2.0, 3.5) if human else 1.5
#             self.scraper.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#             time.sleep(pause)

#             # 3. CHECK FOR NEW CONTENT
#             new_height = self.scraper.execute_script("return document.body.scrollHeight")
            
#             if new_height == last_height:
#                 consecutive_scroll_fails += 1
#                 # Jiggle scroll to trigger lazy load
#                 self.scraper.execute_script("window.scrollBy(0, -300);")
#                 time.sleep(1)
#                 self.scraper.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#                 time.sleep(2)
                
#                 new_height = self.scraper.execute_script("return document.body.scrollHeight")
                
#                 if new_height == last_height and consecutive_scroll_fails >= 3:
#                     print("Reached end of feed or blocked.")
#                     break
#             else:
#                 consecutive_scroll_fails = 0
#                 last_height = new_height

#         # Convert dictionary items to list of tuples: [(text, link), (text, link)]
#         return list(collected_data.items())