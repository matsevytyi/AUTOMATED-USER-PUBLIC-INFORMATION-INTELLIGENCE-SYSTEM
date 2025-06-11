import json
from datetime import datetime
from backend.models import InformationPiece, DiscoverSource, InformationCategory, db
def parse_search_results_to_information_pieces(data, report_id=0):
    """
    Parse the nested search results data and create InformationPiece objects
    """
    information_pieces = []
    
    web_search_source_id = db.session.query(DiscoverSource).filter_by(name="General Web Search").first().id
    platform_scraping_source_id = db.session.query(DiscoverSource).filter_by(name="Social Media").first().id
    
    # flatten the  structure and process each item
    for sublist in data:

        if isinstance(sublist, list):
            for item in sublist:
                if isinstance(item, str) and item.strip():
                    # simple string - facebook scraping
                    info_piece = create_string_information_piece(item, web_search_source_id, report_id)
                    if info_piece:
                        information_pieces.append(info_piece)
                        
                elif isinstance(item, dict):
                    #  structured search results - general web search
                    info_piece = create_dict_information_piece(item, platform_scraping_source_id, report_id)
                    if info_piece:
                        information_pieces.append(info_piece)
    
    # Save all infopieces to database
    for piece in information_pieces:
        db.session.add(piece)
    
    db.session.commit()
    return information_pieces

def create_string_information_piece(content, source_id, report_id):
    """Create InformationPiece from string content"""
    
    return InformationPiece(
        report_id=report_id,
        source_id=source_id,
        source="facebook.com",
        content=content.strip(),
        created_at=datetime.utcnow()
    )

def create_dict_information_piece(item_dict, source_id, report_id):
    """Create InformationPiece from dictionary data"""
    
    # Extract information from the dictionary
    title = item_dict.get('title', '')
    link = item_dict.get('link', '')
    valuable_text = item_dict.get('valuable_text', '')
    
    valuable_text += title
    
    if not valuable_text:
        return
    
    return InformationPiece(
        report_id=report_id,
        source_id=source_id,
        source=link,
        content=valuable_text.strip(),
        created_at=datetime.utcnow()
    )
