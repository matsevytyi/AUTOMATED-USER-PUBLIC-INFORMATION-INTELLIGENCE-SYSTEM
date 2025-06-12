import re

import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from AI_crawler_service import crawler_service

def smart_parse_website(url, user_query):
    
    """
    This function takes a URL and a user query, parses the website with AI (using the crawler service),
    and then formats the output into a JSON object.

    The output JSON object is a dictionary with the following keys:
    - raw: the raw markdown text of the website
    - fit: a list of strings, each representing a "fit" of the user query to the website text.

    If the user query is not found in the website text, the function returns None.
    """
    
    raw, fit = crawler_service.get_markdown(url, user_query)
    
    if isinstance(fit, list):
        return [answer_to_json(fit_text) if fit_text else None for fit_text in fit]
    else:
        return answer_to_json(fit)
    

def answer_to_json(raw_text):
    """
    Converts a raw markdown text to a JSON object.

    The JSON object will have the following keys:
    - name: the name of the link (if present)
    - link: the link URL (if present)
    - title: the title of the page (if present)
    - description: the description of the page (if present)
    - sections: a list of dictionaries, each with the following keys:
        - heading: the heading of the section (in **bold**)
        - content: a list of strings, each representing a line of content in the section
    - resources: a list of dictionaries, each with the following keys:
        - name: the name of the resource (if present)
        - link: the link URL of the resource (if present)

    The function will return None if the input is None or empty.
    """
    
    if not raw_text:
        return None
    
    # name and link from markdown-style link
    result = re.sub(r'\(http[s]?://\S+\)', '', raw_text)
    result = re.sub(r'http[s]?://\S+', '', result)
    result = result.replace('\n', '')
    result = result.replace('*', '')
    result = result.replace('#', '')
    result = re.sub(r'\]', '', result)
    result = re.sub(r'\[', '', result)
    result = re.sub(r'\(javascript:void\\\(0\\\);\)', '', result)

    return result