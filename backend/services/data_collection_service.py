import os
import sys
import threading
from queue import Queue

from backend.services.internal.facebook_scraping_service import FacebookScrapingService

models_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
sys.path.append(models_path)

from backend.services.internal.web_scraping_service import web_scraping_service_singletone
from backend.wrappers.google_search_api_wrapper import search
from backend.services.internal.facebook_scraping_service import FacebookScrapingService
import os
import json

class DataCollectionService:
    def __init__(self):
        self._lock = threading.Lock()
         
         
    def collect_data(self, search_request, use_general=True, use_facebook=True, fb_cookies=None):
        
        results = Queue() 
        threads = []


        if use_facebook:
            threads.append(threading.Thread(target=self._facebook_profiles, args=(search_request, results, fb_cookies)))
            threads.append(threading.Thread(target=self._facebook_search, args=(search_request, results, fb_cookies)))
        
        if use_general:
            threads.append(threading.Thread(target=self._general_scraping, args=(search_request, results)))


        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()
            
        results = list(results.queue)

        return results
    
    # helper functions
    
    def _general_scraping(self, search_request, results):
        
        print("Running general-purpose scraping...")
        
        links_to_be_scraped = []
        answer_links = []
            
        temp_links = search(search_request, num_results=100)
        
        for link in temp_links:
            link["bm25_filter"] = search_request
            
        links_to_be_scraped += temp_links        
                    
        for link in links_to_be_scraped:
            valuable_text = web_scraping_service_singletone.smart_parse_website(link["link"], search_request)
            if valuable_text is None:
                link["valuable_text"] = link["snippet"]
            else:
                link["valuable_text"] = valuable_text
                
            answer_links.append(link)
                
            del link["snippet"] # free memory
        
        results.put(answer_links)
    
    
    def _facebook_profiles(self, search_request, results, cookies):
        print("Scraping Facebook search results...")
        fb_engine = FacebookScrapingService(headless=False)
        try:
            fb_engine.search_and_scrape_profiles_background(search_request=search_request, results=results, cookies=cookies)
        finally:
            try:
                fb_engine.close()
            except Exception:
                pass

    
    def _facebook_search(self, search_request, results, cookies):
        print("Scraping Facebook search results...")
        fb_engine = FacebookScrapingService(headless=False)
        try:
            fb_engine.search_request_background(search_request=search_request, results=results, cookies=cookies)
        finally:
            try:
                fb_engine.close()
            except Exception:
                pass
    

# usage example
# print(get_website_knowledge("Andrii Matsevytyi"))


# Example run:
# results = collect_data("Андрій Мацевитий", use_general=True, use_facebook=True)
# print(results)

    # def _create_temp_cookie_file(self, cookie_map: dict, uid: str = 'tmp') -> str:
    #     """Create a temporary cookies JSON file formatted for the FacebookScraper.
    #     Converts a mapping {'c_user': '..', 'xs': '..'} into a list of cookie dicts
    #     with keys expected by selenium's add_cookie (name, value, domain).
    #     Returns path to the file.
    #     """
    #     if not cookie_map:
    #         return None

    #     cookies_list = []
    #     for k, v in cookie_map.items():
    #         cookies_list.append({'name': k, 'value': v, 'domain': '.facebook.com'})

    #     cookies_dir = os.path.join(os.path.dirname(__file__), 'platform_specific_collection', 'facebook')
    #     os.makedirs(cookies_dir, exist_ok=True)
    #     path = os.path.join(cookies_dir, f'cookies_{uid}.json')
    #     try:
    #         with open(path, 'w') as f:
    #             json.dump(cookies_list, f)
    #         return path
    #     except Exception:
    #         return None

