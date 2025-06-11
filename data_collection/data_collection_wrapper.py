from platform_specific_collection.darkdump import darkdump
from platform_specific_collection.facebook.miner import FacebookScraper
from general_purpose_collection.collect_general_purpose_data import get_website_knowledge as general_scrape
# import general scraping

fb_engine = FacebookScraper(headless=True)

def collect_data(search_request, use_general=True, use_facebook=False, use_darknet=False):
    
    results = []
    
    if use_facebook:
        facebook_data = fb_engine.search_request(query=search_request, amount_of_posts=100)
        results.append(facebook_data)
        
    if use_darknet:
        darknet_data = darkdump.Darkdump().crawl(query=search_request, amount=100, scrape_sites=True, extract_full_text=True)
        results.append(darknet_data)
    
    if use_general:
        general_data = general_scrape(query=search_request)
        results.append(general_data)
    
    return results

a = collect_data("Andrii Matsevytyi", use_general=True,use_darknet=True, use_facebook=True)
print(a)