from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

import time
import random
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import process_data as pdt

class FacebookScraper:
    def __init__(self, chrome_driver_path='/opt/homebrew/bin/chromedriver', headless=True, cookie_path="cookies.json"):
        self.chrome_driver_path = chrome_driver_path
        self.headless = headless
        self.cookie_path = cookie_path
        self.scraper = self._prepare_scraper()
        self.cookies = self._load_cookies()

    def _prepare_scraper(self):
        options = Options()
        if self.headless:
            options.add_argument('--headless')

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        return driver

    def _load_cookies(self):
        full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.cookie_path)
        with open(full_path, "r") as file:
            try:
                return json.load(file)
            except Exception:
                raise Exception(f"Failed to load cookies from {full_path}")

    def _apply_cookies(self, url):
        self.scraper.get(url)
        for cookie in self.cookies:
            self.scraper.add_cookie(cookie)
        
        # c_user and sb cookies are constant    
            
        self.scraper.refresh()
        time.sleep(3)
        
    def extract_and_filter_profiles(self, links_soup):
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
        
    def obtain_profiles(self, user_name_surname):
        
        url = f"https://www.facebook.com/search/people/?q={user_name_surname}"
                
        self._apply_cookies(url)
        last_height = self.scraper.execute_script("return document.body.scrollHeight")
        soup = BeautifulSoup(self.scraper.page_source, 'html.parser')
        
        links = []

        for a_tag in soup.find_all("a", href=True):
            
            href = a_tag['href']
            links.append(href)
        
        profile_links = self.extract_and_filter_profiles(links)
        
        return list(set(profile_links))

    def scrape_page(self, url, amount_of_posts=50, human=True):
        self._apply_cookies(url)
        posts = []

        last_height = self.scraper.execute_script("return document.body.scrollHeight")
        for i in range(amount_of_posts):
            pause = random.uniform(1.7, 1.1) if human else random.uniform(0.4, 0.5)
            self.scraper.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)

            if i % 10 == 0:
                print(f"Loaded {i} posts")

            new_height = self.scraper.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("Reached the end of the posts")
                break
            last_height = new_height

        print("All posts loaded. Expanding 'See more'...")

        try:
            buttons = self.scraper.find_elements(By.XPATH, "//div[contains(text(),'See more')]")
            for btn in buttons:
                try:
                    self.scraper.execute_script("arguments[0].click();", btn)
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Error clicking 'See More': {e}")
        except Exception as e:
            print(f"Error finding 'See More' buttons: {e}")

        soup = BeautifulSoup(self.scraper.page_source, 'html.parser')
        divs = soup.find_all("div", {"data-ad-rendering-role": "story_message"})

        for div in divs:
            text = div.get_text(strip=True)
            posts.append(text)

        print(f"Collected {len(posts)} posts")
        return posts

    def close(self):
        self.scraper.quit()

    def search_profile(self, profile_url, amount_of_posts=50, human=True):
        return self.scrape_page(url=profile_url, amount_of_posts=amount_of_posts, human=human)

    def search_request(self, query, amount_of_posts=50, human=True):
        url = f"https://www.facebook.com/search/posts/?q={query}"
        return self.scrape_page(url=url, amount_of_posts=amount_of_posts, human=human)

if __name__ == '__main__':
    # Example arguments (replace with argparse or CLI input in real usage)
    # url = "https://www.facebook.com/search/posts/?q=Андрій Мацевитий"
    # amount_to_scrape = 50
    # recursive_depth = 0

    fb = FacebookScraper(headless=False)

    # print("Scraping posts...")
    # #posts = fb.scrape_page(url, amount_of_posts=amount_to_scrape)
    posts = fb.obtain_profiles("Andrii Matsevytyi")

    fb.close()
    print(posts)
    

    # print("Processing posts...")

    # summary = pdt.generate_summary(posts)
    # key_info = pdt.extract_key_info(posts)

    # print("\nSummary:")
    # print(summary)

    # print("\nKey Info:")
    # print(key_info)

    # if recursive_depth > 0:
    #     print("Running recursively...")
    #     for i in range(recursive_depth):
    #         print(f"Iteration {i+1}...")
    #         time.sleep(3)
    #         # You can re-use fb.search_profile or search_request with new arguments
    #         print("No information found, stopping recursion.")
