from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

import os, sys
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from google_search_with_api import search
from parse_website_with_AI import smart_parse_website

def get_website_knowledge(query):
    
    final_links = []
    links_to_be_scraped = []
        
    temp_links = search(query, num_results=50)
    
    print(temp_links)
    
    for link in temp_links:
        link["bm25_filter"] = query
        
    links_to_be_scraped += temp_links        
                
    for link in links_to_be_scraped:
        valuable_text = smart_parse_website(link["link"], link["bm25_filter"])
        if valuable_text is None:
            link["valuable_text"] = link["snippet"]
        else:
            link["valuable_text"] = valuable_text
                
        final_links.append(link)
            
        del link["snippet"]
    
    return final_links

# usage example
# print(get_website_knowledge("Andrii Matsevytyi"))
