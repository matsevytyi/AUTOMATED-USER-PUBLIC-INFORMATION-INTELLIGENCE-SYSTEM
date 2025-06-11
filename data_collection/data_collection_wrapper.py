from platform_specific_collection.darkdump import darkdump
from platform_specific_collection.facebook.miner import FacebookScraper
from general_purpose_collection.collect_general_purpose_data import get_website_knowledge as general_scrape

# TODO: verify it works
# cache user-related profiles
# extract data on data processing
# make unified formatting
# prompt llm on recommendations
# connect end-to-end with frontend

# data verification platform (?) (real or mock)?

fb_engine = FacebookScraper(headless=True)

def collect_data(search_request, use_general=True, use_facebook=False, use_darknet=False):
    
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

a = collect_data("Андрій Мацевитий", use_general=True,use_darknet=True, use_facebook=True)
print(a)