import requests
import json
import os

# load necessary keys
GOOGLE_API_KEY = os.getenv("GOGL_CUSTOM_SEARCH_API_KEY") # free usage - 100\day
GOOGLE_CX = os.getenv("GOOGLE_CX")

print(f"GOOGLE_API_KEY retrieved: {GOOGLE_API_KEY[:4]}...{GOOGLE_API_KEY[-4:]}")
print(f"GOOGLE_CX retrieved: ...{GOOGLE_CX[-4:]}")

# list of trusted domains
TRUSTED_DOMAINS = [
    "mitre.org",
    "nist.gov",
    "owasp.org",
    "cybersecurity.att.com",
    "cisa.gov"
]

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
        f"https://www.googleapis.com/customsearch/v1?"
        f"q={query}&key={GOOGLE_API_KEY}&cx={GOOGLE_CX}&num={num_results}"
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
                "trusted": any(domain in item["link"] for domain in TRUSTED_DOMAINS),
            }
        )

    return links

# Usage: 1/request (not N=num_results) - dependant on search()
def search_trusted_domains(query, num_results = 5): 
    """
    Performs Google search only within allowed domains.
    
    Relies on search(query, num_results)
    
    """
    
    domain_filter = " OR ".join([f"site:{domain}" for domain in TRUSTED_DOMAINS])
    filtered_query = f"{query} ({domain_filter})"

    
    return search(filtered_query, num_results)

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

# sample answer to search_trustred_domains function
"""
[
    {'title': 'Phishing | NIST', 'link': 'https://www.nist.gov/itl/smallbusinesscyber/guidance-topic/phishing', 'snippet': 'Oct 22, 2021 ... Phishing is the use of convincing emails or other messages to trick us into opening harmful links or downloading malicious software.', 'trusted': True}, 
    {'title': 'Recognize and Report Phishing | CISA', 'link': 'https://www.cisa.gov/secure-our-world/recognize-and-report-phishing', 'snippet': 'Phishing occurs when criminals try to get us to open harmful links, emails or attachments that could request our personal information or infect our devices.', 'trusted': True}, 
    {'title': 'Avoiding Social Engineering and Phishing Attacks | CISA', 'link': 'https://www.cisa.gov/news-events/news/avoiding-social-engineering-and-phishing-attacks', 'snippet': 'Feb 1, 2021 ... What is a phishing attack? Phishing is a form of social engineering. Phishing attacks use email or malicious websites to solicit personal\xa0...', 'trusted': True}, 
    {'title': 'Shields Up: Guidance for Families | CISA', 'link': 'https://www.cisa.gov/shields-guidance-families', 'snippet': "More than 90% of successful cyber-attacks start with a phishing email. A phishing scheme is when a link or webpage looks legitimate, but it's a trick\xa0...", 'trusted': True}, 
    {'title': 'phishing - Glossary | CSRC', 'link': 'https://csrc.nist.gov/glossary/term/phishing', 'snippet': 'A technique for attempting to acquire sensitive data, such as bank account numbers, through a fraudulent solicitation in email or on a web site.', 'trusted': True}
    ] 
"""