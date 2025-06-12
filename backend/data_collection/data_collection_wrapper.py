import os
import sys

models_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
sys.path.append(models_path)

from backend.data_collection.platform_specific_collection.darkdump import darkdump
from backend.data_collection.platform_specific_collection.facebook.miner import FacebookScraper
from backend.data_collection.general_purpose_collection.collect_general_purpose_data import get_website_knowledge as general_scrape

fb_engine = FacebookScraper(headless=True)

def collect_data(search_request, use_general=True, use_facebook=True, use_darknet=False):
    
    results = []
    
    if use_facebook:
        # general request details
        print("Sraping search results")
        facebook_data = fb_engine.search_request(query=search_request, amount_of_posts=100)
        results.append(facebook_data)
        
        user_profiles = fb_engine.obtain_profiles(search_request)
        
        # specific profile details
        for profile in user_profiles:
            print("scraping profile" , profile)
            facebook_profile_data = fb_engine.search_profile(profile, amount_of_posts=100)
            results.append(facebook_profile_data)
        
    if use_darknet:
        darknet_data = darkdump.Darkdump().crawl(query=search_request, amount=100, scrape_sites=True, extract_full_text=True)
        results.append(darknet_data)
    
    if use_general:
        general_data = general_scrape(query=search_request)
        results.append(general_data)
    
    return results

# a = collect_data("Андрій Мацевитий", use_general=True,use_darknet=True, use_facebook=True)
# print(a)