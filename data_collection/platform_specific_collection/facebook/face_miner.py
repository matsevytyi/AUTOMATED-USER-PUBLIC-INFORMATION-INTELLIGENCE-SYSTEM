from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup
import time

import random
import json

import os

import argparse

import process_data as pdt

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Welcome to Intelligent NLP-powered Facebook scraper",
        epilog="Developed by Andrii Matsevytyi"
    )
    
     # facebook scraping
    facebook_group = parser.add_argument_group("Facebook scraping options")
    facebook_group.add_argument("--profile", type=str, help="URL of the profile to scrape.")
    facebook_group.add_argument("--search", type=str, help="Search query to scrape (expect plaintext string)")
    facebook_group.add_argument("--amount", type=int, default=30, help="Number of posts to scrape.")
    facebook_group.add_argument("--iteramnt", type=int, default=0, help="Amount of recursive searches of extracted data.")
    
    # applying NLP
    nlp_group = parser.add_argument_group("NLP application options")
    nlp_group.add_argument("--summary", action="store_true", help="Generate a summary")
    nlp_group.add_argument("--keyinfo", action="store_true", help="Extract key info (links, emails, phones)")
    nlp_group.add_argument("--people", action="store_true", help="Extract people (names/surnames)")
    nlp_group.add_argument("--events", action="store_true", help="Extract event details")
    nlp_group.add_argument("--all", action="store_true", help="Load all available data")

    return parser.parse_args()

def load_cookies(filename="cookies.json"):
    
    current_directory = os.path.dirname(os.path.abspath(__file__))
    
    # Create a path for the cookies file in the "resources" folder
    resources_directory = os.path.join(current_directory, "../resources")
    
    # Full path to save the cookies file
    filename = os.path.join(resources_directory, filename)
    
    with open(filename, "r") as file:
        try:
            file = json.load(file)
        except:
            raise Exception(f"Failed to load cookies file. Make sure you inserted cookies into {filename}")
        
        return file

def prepare_scraper(chrome_driver_path = '/opt/homebrew/bin/chromedriver', headless=True):
    
    chrome_service = Service(chrome_driver_path)
    chrome_options = Options()
    
    # stealth mode, default
    if headless: chrome_options.add_argument('--headless') 

    return webdriver.Chrome(service=chrome_service, options=chrome_options)
    
def scrape_page(scraper, url, amount_of_posts, cookies, human=True):
    
    all_posts = []
    scraper.get(url)
    
    # apply cookie hijacking to avoid scraping detection
    for cookie in cookies:
        scraper.add_cookie(cookie)

    scraper.refresh()

    time.sleep(3)
    
    
    last_height = scraper.execute_script("return document.body.scrollHeight")
    
    for i in range(amount_of_posts):
        
        scroll_pause_time = random.uniform(1.1, 1.2) if human else random.uniform(0.4, 0.5)
    
        scraper.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        time.sleep(scroll_pause_time)
        
        if i % 10 == 0:
            print(f"Loaded {i} posts")
        
        # new scroll heightvs the last height
        new_height = scraper.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            # no more content is loaded, break the loop
            "reached the end of the posts"
            break
        last_height = new_height
        
    print("All posts loaded.")

    # the final page source code
    page_source = scraper.page_source

    # parse out the tags
    soup = BeautifulSoup(page_source, 'html.parser')


    # Locate "See More" buttons and click them
    try:
        see_more_buttons = scraper.find_elements(By.XPATH, "//div[contains(text(),'See more')]")
        print(see_more_buttons[0].text)
        for button in see_more_buttons:
            try:
                #button.click()
                #print(button.is_displayed(), button.is_enabled())
                #scraper.execute_script("arguments[0].scrollIntoView(true);", button)
                scraper.execute_script("arguments[0].click();", button)
                time.sleep(0.5)  # Allow time for the content to expand
            except Exception as e:
                print(f"Error clicking 'See More': {e}")
    except Exception as e:
        print(f"Error finding 'See More' buttons: {e}")

    # locate the part with divs, where facebook stores post text
    target_divs = soup.find_all("div", {"data-ad-rendering-role": "story_message"})

    for div in target_divs:
        text = div.get_text(strip=True)
        #print("\n", text)
        all_posts.append(text)
    
    print("Parsing out empty posts and ads...")  
    time.sleep(1.5)
    print("Collected posts without ads:", len(all_posts))
        
    return all_posts
        
def close_scraper(scraper):
    scraper.quit()

if __name__ == '__main__':
    
    args = parse_arguments()
    
    if args.profile:
        url = args.profile
        print(f"Scraping profile: {url}")
    elif args.search:
        url = f"https://www.facebook.com/search/top?q={args.search}"
        print(f"Scraping search results for: {args.search}")
    else:
        print("Error: Either --profile or --search must be provided.")
        exit(1)
        
    amount_to_scrape = args.amount
    
    recursive_depth = args.iteramnt
    
    scraper = prepare_scraper(headless=True)
    
    print("Initiated the scraper")
    
    #url = "https://www.facebook.com/profile.php?id=100023014805164"
    #url = 'https://www.facebook.com/adidas'
    #url = "https://www.facebook.com/bogdan.pasiuk"

    # Example usage
    cookies = load_cookies("../resources/cookies.json")
    
    posts = scrape_page(scraper=scraper, url=url, amount_of_posts=amount_to_scrape, cookies=cookies)
    
    close_scraper(scraper=scraper)
    
    print("Processing posts...")
    
    if args.all:
        for post in posts:
            print("\n", post)
    else:
        if args.summary:
            print("Summarising...")
            summary = pdt.generate_summary(posts)
            print("\nSummary:")
            print(summary)
        if args.keyinfo:
            print("Extracting key info...")
            
            key_info = pdt.extract_key_info(posts)
            print("\nKey Info (Links, Emails, Phones):")
            
            print("Phones:")
            if len(key_info.get("phones")) == 0 and len(key_info.get("emails")) == 0 and len(key_info.get("links")) == 0:
                print("\tNo phone numbers info found")
            for phone in key_info.get("phones"):
                print("\t" + phone) 
                
            print("Emails:")
            if len(key_info.get("emails")) == 0:
                print("\tNo emails found")
            for email in key_info.get("emails"):
                print("\t" + email) 
                 
            print("Links:")
            if len(key_info.get("links")) == 0:
                print("\tNo links found")
            for link in key_info.get("links"):
                print("\t" + link)
        if args.people:
            people = pdt.extract_people(posts)
            print("People (Names/Surnames):")
            print(people)
        if args.events:
            print("Identifying events...")
            events = pdt.extract_events(posts)
            print("\nEvents:")
            for event in events:
                print("\nWhere: ", event.get("where"), "\nWhen: ", event.get("dateTime"), "\nPeople: ", event.get("people"), "\nDetails: ", event.get("details"), "\n",)
    
    #I just want to call the application recursively but with extractred arguments from keyinfo and people
    if recursive_depth > 0:
        print("Running the application recursively...")
        for i in range(recursive_depth):
            print(f"Starting {i+1} iteration...")
            time.wait(3)
            print("No information found, stopping the recursions")
        
    print("\nFinished successfully\n")