import requests
import os

from dotenv import load_dotenv
load_dotenv()

# load necessary keys
GOOGLE_API_KEY = os.getenv("GOGL_CUSTOM_SEARCH_API_KEY") # free usage - 100\day
GOOGLE_CX = os.getenv("GOOGLE_CX")

print(f"GOOGLE_API_KEY retrieved: {GOOGLE_API_KEY[:4]}...{GOOGLE_API_KEY[-4:]}")
print(f"GOOGLE_CX retrieved: ...{GOOGLE_CX[-4:]}")

# headers for reusable searching
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Usage: 1 request (not N=num_results)
def search(query: str, num_results: int = 5) -> list:
    """
    Search Google Custom Search API and return top-N results.

    Args:
        query (str): Search query
        num_results (int): Number of results to return

    Returns:
        list: List of dictionaries with title, link, snippet, and trusted flag
    """
    url = (
        f"https://www.googleapis.com/customsearch/v1?&key={GOOGLE_API_KEY}&cx={GOOGLE_CX}&q={query}"
    )
    
    response = requests.get(url, headers=headers)
    
    results = response.json()

    links = []
    for item in results.get("items", []):
        links.append(
            {
                "title": item["title"],
                "link": item["link"],
                "snippet": item["snippet"],
            }
        )

    return links

# sample answer to search function
"""
[
    {'title': 'How To Recognize and Avoid Phishing Scams | Consumer Advice', 'link': 'https://consumer.ftc.gov/articles/how-recognize-and-avoid-phishing-scams', 'snippet': 'Scammers use email or text messages to try to steal your passwords, account numbers, or Social Security numbers. If they get that information, they could get\xa0...', 'trusted': False}, 
    {'title': 'Protect yourself from phishing - Microsoft Support', 'link': 'https://support.microsoft.com/en-us/windows/protect-yourself-from-phishing-0c7ea947-ba98-3bd9-7184-430e1f860a44', 'snippet': 'Here are some ways to recognize a phishing email: Urgent call to action or threats - Be suspicious of emails and Teams messages that claim you must click, call,\xa0...', 'trusted': False}, 
    {'title': 'Spoofing and Phishing — FBI', 'link': 'https://www.fbi.gov/how-we-can-help-you/scams-and-safety/common-frauds-and-scams/spoofing-and-phishing', 'snippet': 'Spoofing is when someone disguises an email address, sender name, phone number, or website URL—often just by changing one letter, symbol, or number\xa0...', 'trusted': False}, 
    {'title': 'Avoid and report phishing emails - Gmail Help', 'link': 'https://support.google.com/mail/answer/8253?hl=en', 'snippet': 'Report an email as phishing · On a computer, go to Gmail. · Open the message. · Next to Reply , click More More . · Click Report phishing. Report\xa0...', 'trusted': False}, 
    {'title': 'Phishing: Spot and report scam emails, texts, websites and ...', 'link': 'https://www.ncsc.gov.uk/collection/phishing-scams', 'snippet': "'Phishing' is when criminals use scam emails, text messages or phone calls to trick their victims. The aim is often to make you visit a website.", 'trusted': False}
    ] 
"""