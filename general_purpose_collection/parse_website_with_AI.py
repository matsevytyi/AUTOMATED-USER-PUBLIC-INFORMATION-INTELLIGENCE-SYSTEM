import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)+"/../../../../"))

import re
import json

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

#smart_parse_website(["https://www.nist.gov/itl/smallbusinesscyber/guidance-topic/phishing", "https://www.nist.gov/itl/smallbusinesscyber"], "phishing")

# example of FIT data retrieved based on phishing

"""
[Phishing](https://www.nist.gov/itl/smallbusinesscyber/guidance-topic/phishing)
# Phishing
Protecting Your Small Business: Phishing
Phishing is the use of convincing emails or other messages to trick us into opening harmful links or downloading malicious software. These messages are often disguised as a trusted source, such as your bank, credit card company, or even a leader within your own business.
**How to Spot a Phish**
Artificial intelligence (AI) can now be used to craft increasingly convincing phishing attacks, so it is more imperative than ever to take a second, or third, look at any message requesting you to take action—such asking you to click a link, download a file, transfer funds, log into an account, or submit sensitive information.What to look out for:
* Teach employees how to spot and report a phish when they have fallen victim or think they have fallen victim to a phishing attack.
* Don’t engage with the sender, and do not click any link in the email (including unsubscribe). Just delete the message. You can report phishing crimes to the FBI’s Internet Crime Complaint Center.
* Deploy and maintain anti-virus software – if the phishing attack aims to install malware on your computer, up-to-date anti-virus software may help prevent the malware from installing.
* Utilize email filters – many email services have configurable filters that can help prevent many phishing messages from ever reaching your employees’ mailboxes.
**What should I do if I think I’ve been a victim of a phishing attack?**
* **Contact the fraud department of the breached account** – If the phishing attack compromised your company’s account at a financial institution, contact the bank immediately to report the incident. Monitor for unauthorized transactions to the account. If a personal account was involved, contact the 3 major credit bureaus to enable fraud alerts.
* Are we regularly training employees to raise their awareness of phishing threats?
* Do our employees know how to report if they think they have fallen victim to a phishing attack?
* NIST Human-Centered Cybersecurity Phishing Resources:[https://csrc.nist.gov/projects/human-centered-cybersecurity/research-areas/phishing](https://csrc.nist.gov/projects/human-centered-cybersecurity/research-areas/phishing)
* Recognize and Report Phishing (Cybersecurity and Infrastructure Security Agency)[https://www.cisa.gov/secure-our-world/recognize-and-report-phishing](https://www.cisa.gov/secure-our-world/recognize-and-report-phishing)
"""

# example of parsed data

"""
{
    "name": "Phishing",
    "link": "https://www.nist.gov/itl/smallbusinesscyber/guidance-topic/phishing",
    "title": "Phishing",
    "description": "Protecting Your Small Business: Phishing\nPhishing is the use of convincing emails or other messages to trick us into opening harmful links or downloading malicious software.",
    "sections": [
        {
            "heading": "How to Spot a Phish",
            "content": [
                "* AI can now be used to craft increasingly convincing phishing attacks...",
                "* Teach employees how to spot and report a phish...",
                "* Don\u2019t engage with the sender, and do not click any link...",
                "* Deploy and maintain anti-virus software...",
                "* Utilize email filters..."
            ]
        },
        {
            "heading": "What should I do if I think I\u2019ve been a victim of a phishing attack?",
            "content": [
                "* Contact the fraud department of the breached account...",
                "* Are we regularly training employees...",
                "* Do our employees know how to report phishing attacks?",
                "* NIST Human-Centered Cybersecurity Phishing Resources [https://csrc.nist.gov/projects/human-centered-cybersecurity/research-areas/phishing](https://csrc.nist.gov/projects/human-centered-cybersecurity/research-areas/phishing)",
                "* Recognize and Report Phishing (CISA) [https://www.cisa.gov/secure-our-world/recognize-and-report-phishing](https://www.cisa.gov/secure-our-world/recognize-and-report-phishing)"
            ]
        }
    ],
    "resources": [
        {
            "name": "Phishing",
            "link": "https://www.nist.gov/itl/smallbusinesscyber/guidance-topic/phishing"
        },
        {
            "name": "https://csrc.nist.gov/projects/human-centered-cybersecurity/research-areas/phishing",
            "link": "https://csrc.nist.gov/projects/human-centered-cybersecurity/research-areas/phishing"
        },
        {
            "name": "https://www.cisa.gov/secure-our-world/recognize-and-report-phishing",
            "link": "https://www.cisa.gov/secure-our-world/recognize-and-report-phishing"
        }
    ]
}
"""