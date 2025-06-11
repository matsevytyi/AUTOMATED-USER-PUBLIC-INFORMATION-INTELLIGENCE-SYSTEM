#from transformers import pipeline
import re
from datetime import datetime
from collections import Counter
import spacy
nlp = spacy.load("en_core_web_sm")

def generate_summary(posts):
    """
    Generate a simple extractive summary of posts using SpaCy.
    """
    #  all posts into a single string
    full_text = " ".join(posts)
    
    #  the text with SpaCy
    doc = nlp(full_text)
    
    # the most frequent nouns and named entities
    word_frequencies = Counter()
    for word in doc:
        if word.is_alpha and not word.is_stop and word.pos_ in {"NOUN", "PROPN"}:
            word_frequencies[word.text.lower()] += 1
    
    # Normalize frequencies
    max_freq = max(word_frequencies.values())
    for word in word_frequencies:
        word_frequencies[word] /= max_freq
    
    #  sentences based on word frequencies
    sentence_scores = {}
    for sent in doc.sents:
        for word in sent:
            if word.text.lower() in word_frequencies:
                sentence_scores[sent] = sentence_scores.get(sent, 0) + word_frequencies[word.text.lower()]
    
    # top N sentences for the summary
    num_sentences = min(5, len(sentence_scores))  # Select up to 5 sentences
    summary_sentences = sorted(sentence_scores, key=sentence_scores.get, reverse=True)[:num_sentences]
    
    # sentences into the final summary
    summary = " ".join([sent.text for sent in summary_sentences])
    
    return summary

def extract_key_info(posts):
    # regular expressions for links, emails, and phone numbers
    url_pattern = r'https?://[^\s]+'
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'\+?[0-9]{1,4}?[-.\s]?[0-9]+[-.\s]?[0-9]+[-.\s]?[0-9]+'

    links = []
    emails = []
    phones = []

    for post in posts:
        links += re.findall(url_pattern, post)
        emails += re.findall(email_pattern, post)
        phones += re.findall(phone_pattern, post)
    
    return {
        "links": links,
        "emails": emails,
        "phones": phones
    }


def extract_people(posts):
    people = []
    for post in posts:
        doc = nlp(post)
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                people.append(ent.text)
    
    return people

def extract_events(posts):
    events = []
    event_keywords = ['event', 'party', 'meetup', 'conference']

    for post in posts:
        # Look for keywords indicating an event
        if any(keyword in post.lower() for keyword in event_keywords):
            event = {}
            # Extract event name (simple assumption based on the post structure)
            event["details"] = post.split("\n")[0]  # Assume the first line is the event name
            # Extract date and time (you may need a more sophisticated date extractor)
            try:
                date_time = re.search(r'(\d{1,2} \w+ \d{4}|\d{1,2} \w+ \d{1,2} \d{4} \d{1,2}:\d{2})', post)
                if date_time:
                    event["dateTime"] = date_time.group(0)
                else:
                    event["dateTime"] = "Not found"
            except Exception as e:
                event["dateTime"] = "Error extracting date"
            
            # Extract location (simple heuristic for "where" or location keywords)
            location = re.search(r'(where|at)\s+([a-zA-Z\s]+)', post)
            if location:
                event["where"] = location.group(2)
            else:
                event["where"] = "Location not found"
            
            # people attending (simple assumption of names or specific phrases)
            people = re.findall(r'(?:attending|with)\s+([a-zA-Z\s]+)', post)
            event["people"] = people

            events.append(event)
    
    return events