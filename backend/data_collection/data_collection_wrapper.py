import os
import sys
import threading

models_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
sys.path.append(models_path)

from backend.data_collection.platform_specific_collection.darkdump import darkdump
from backend.data_collection.platform_specific_collection.facebook.miner import FacebookScraper
from backend.data_collection.general_purpose_collection.collect_general_purpose_data import get_website_knowledge as general_scrape

fb_engine = FacebookScraper(headless=True)

def facebook_search(search_request, results):
    print("Scraping Facebook search results...")
    facebook_data = fb_engine.search_request(query=search_request, amount_of_posts=100)
    results.append(facebook_data)

def facebook_profiles(search_request, results):
    print("Obtaining Facebook profiles...")
    user_profiles = fb_engine.obtain_profiles(search_request)
    for profile in user_profiles:
        print("Scraping Facebook profile:", profile)
        profile_data = fb_engine.search_profile(profile, amount_of_posts=100)
        results.append(profile_data)

def general_scraping(search_request, results):
    print("Running general-purpose scraping...")
    general_data = general_scrape(query=search_request)
    results.append(general_data)

def collect_data(search_request, use_general=True, use_facebook=True, use_darknet=False):
    results = []

    threads = []

    if use_facebook:
        threads.append(threading.Thread(target=facebook_search, args=(search_request, results)))
        threads.append(threading.Thread(target=facebook_profiles, args=(search_request, results)))

    if use_general:
        threads.append(threading.Thread(target=general_scraping, args=(search_request, results)))

    if use_darknet:
        print("Running darknet scraping...")
        darknet_data = darkdump.Darkdump().crawl(
            query=search_request, amount=100, scrape_sites=True, extract_full_text=True
        )
        results.append(darknet_data)

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    return results

# Example run:
# results = collect_data("Андрій Мацевитий", use_general=True, use_darknet=True, use_facebook=True)
# print(results)
