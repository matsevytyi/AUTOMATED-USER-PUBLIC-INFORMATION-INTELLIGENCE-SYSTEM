import re
from datetime import datetime
from transformers import pipeline
from sentence_transformers import SentenceTransformer, util
from rapidfuzz import fuzz

from backend.models import InformationPiece, InformationCategory, DiscoverSource
from backend.utils.config import Config


class DataProcessingEngine:
    """
    Singleton engine for Data Processing
    Handles Normalization, NER, Regex, Validation, and Canonization.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DataProcessingEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        print("[INIT] Loading NER Model...")
        # NER must be done with pretrained sequence labeling model (e.g. BERT)
        self.ner_pipeline = pipeline("ner", model=Config.NER_MODEL, grouped_entities=True)
        
        print("[INIT] Loading Semantic Model...")
        self.semantic_model = SentenceTransformer(Config.SEMANTIC_MODEL)
        
        self.categories_cache = {}
        self._initialized = True

    def process_raw_data(self, data_list, report_id, report_query, db):
        """
        Main pipeline entry point corresponding to DFD Level 2.
        """
        processed_pieces = []
        seen_hashes = set() # Local cache for deduplication
        
        # 1. Normalization & Flattening
        # "Entries must be normalized by removing diverse quoting and punctuation"
        clean_entries = self._normalize_inputs(data_list)

        for entry in clean_entries:
            text = entry['text']
            source = entry['source']
            
            # 2. Entity Extraction (NER + Regex)
            candidates = self._extract_candidates(text)
            
            for val_text, cat_type, method in candidates:
                
                # 3. Rule-based Validation
                # - Not matching input query (Levenshtein)
                # - Minimal length (3)
                if not self._validate_rules(val_text, report_query, cat_type):
                    continue
                
                # 4. Vector Embedding & Comparison
                # "Compare against topic-specific reference phrase"
                similarity = self._vector_validation(val_text, cat_type)
                
                # 5. Post-processing Canonization
                final_text = self._canonize(val_text, cat_type)
                
                # 6. Merge & Deduplicate (Local Check)
                # "They are merged and dedublicated (checked against local report-wide cache)"
                content_hash = f"{final_text}|{cat_type}"
                if content_hash in seen_hashes:
                    continue
                seen_hashes.add(content_hash)
                
                # Save to DB
                piece = self._create_information_piece(
                    db, final_text, cat_type, source, report_id, similarity, text
                )
                processed_pieces.append(piece)
                
        db.session.commit()
        return processed_pieces

    def _normalize_inputs(self, data):
        """Flatten nested lists and normalize text."""
        normalized = []
        
        def clean(s):
            # removing diverse quoting and punctuation symbols or extra whitespace
            s = re.sub(r'["\'`«»]', '', s) 
            s = re.sub(r'\s+', ' ', s)
            return s.strip()

        for item in data:
            # Handle list of lists structure from scraping service
            if isinstance(item, list):
                for subitem in item:
                    if isinstance(subitem, dict):
                        text = (subitem.get('valuable_text') or "") + " " + (subitem.get('title') or "")
                        normalized.append({'text': clean(text), 'source': subitem.get('link', 'Web Search')})
                    elif isinstance(subitem, str):
                        normalized.append({'text': clean(subitem), 'source': 'Social Media'})
            elif isinstance(item, dict):
                 text = (item.get('valuable_text') or "") + " " + (item.get('title') or "")
                 normalized.append({'text': clean(text), 'source': item.get('link', 'Web Search')})
                 
        return normalized

    def _extract_candidates(self, text):
        """Combine NER and Regex extraction."""
        candidates = [] # List of (text, category, method)
        
        # A. NER Extraction
        try:
            ner_results = self.ner_pipeline(text[:512]) # Limit for BERT
            for entity in ner_results:
                word = entity['word']
                group = entity['entity_group']
                
                if group == 'PER': cat = 'Social Connections'
                elif group == 'ORG': cat = 'Professional Details'
                elif group == 'LOC': cat = 'Location Data'
                else: cat = 'Uncategorized'
                
                candidates.append((word, cat, 'NER'))
        except Exception:
            pass

        # B. Regex Extraction
            
         # 2. Emails
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
        candidates.extend([(email, 'contact_info', 'REGEX') for email in emails])
        
        # 3. Financial info (keywords or patterns like $1000, UAH, etc.)
        financial = re.findall(r'\$\d+(?:,\d{3})*(?:\.\d{2})?|\b(?:UAH|EUR|USD|грн|долар|євро|euro|buck|dollar|$|€|£)\b', text)
        candidates.extend([(fin, 'financial_info', 'REGEX') for fin in financial])

        # 4. Phone numbers (with extended cases support)
        phones = re.findall(r'(\+?\d[\d\-\s()]{7,}\d)', text)
        candidates.extend([(phone, 'contact_info', 'REGEX') for phone in phones])

        # 5. Social media (usernames or links)
        social = re.findall(r' @\S+', text)
        candidates.extend([(item, 'contact_info', 'REGEX') for item in social])
        
        # 6. Professional titles (simple keyword match)
        professions = ['CEO', 'founder', 'developer', 'manager', 'engineer', 'analyst', 'specialist', 'student']
        for prof in professions:
            if re.search(r'\b' + re.escape(prof) + r'\b', text, re.IGNORECASE):
                candidates.append((prof, 'professional', 'REGEX'))

        # 7. Public statements (e.g., quotes or keywords like "said", "tweeted")
        if re.search(r'\b(said|stated|tweeted|posted|commented)\b', text, re.IGNORECASE):
            candidates.append((text, 'public_statement', 'REGEX'))

        # 8. Other personal identifiers (passport, ID, etc. — extend as needed)
        identifiers = re.findall(r'\bID[:\s]*\d+|passport[:\s]*\w+\d+', text, re.IGNORECASE)
        candidates.extend([(id_val, 'personal_identifier', 'REGEX') for id_val in identifiers])

        return candidates

    def _validate_rules(self, text, query, category):
        """
        Rule-based validation:
        1. Min length 3
        2. Not matching input query (Levenshtein)
        """
        
        text = text.replace("#", "")
            
        # if entity_type == "social_connections" and not " " in word:
        #     continue
        
        if len(text) < 3:
            return False
        
        if category == "contact_info":
            return True
        
        if text.lower() in query.lower() or query.lower() in text.lower():
            return False
            
        # Levenshtein check
        if query:
            ratio = fuzz.ratio(text.lower(), query.lower())
            if ratio > 85: # Threshold
                return False
                
        return True

    def _vector_validation(self, text, category):
        """
        Compare against topic-specific reference phrase using cosine similarity.
        """
        # Reference phrases for validation
        refs = {
            'Social Connections': 'person individual friend human',
            'Professional Details': 'company organization business job work',
            'Location Data': 'city country place address street',
            'Contact Information': 'email phone contact number',
            'Financial Information': 'money price cost salary dollar'
        }
        
        ref_phrase = refs.get(category, 'general entity')
        
        emb1 = self.semantic_model.encode(text, convert_to_tensor=True)
        emb2 = self.semantic_model.encode(ref_phrase, convert_to_tensor=True)
        
        return float(util.cos_sim(emb1, emb2).item())

    def _canonize(self, text, category):
        """Post-processing canonization (e.g. phone numbers)."""
        if category == 'Contact Information' and any(c.isdigit() for c in text):
            # Remove spaces, dashes, brackets
            return re.sub(r'[\s\-\(\)]', '', text)
        return text

    def _create_information_piece(self, db, content, cat_name, source, report_id, score, snippet):
        # Resolve Category ID            
        if cat_name not in self.categories_cache:
            cat = db.session.query(InformationCategory).filter_by(name=cat_name).first()
            if not cat:
                cat = InformationCategory(name=cat_name, weight=0.5)
                db.session.add(cat)
                db.session.commit()
            self.categories_cache[cat_name] = cat.id
            
        # Resolve Source ID
        
        if source:
            discovered_from = "Web Data"
            if "facebook.com" in source:
                discovered_from = "Social Media"
        else:
            discovered_from = "Social Media"
        
        src = db.session.query(DiscoverSource).filter_by(name=discovered_from).first()
        if not src:
            src = DiscoverSource(name=discovered_from)
            db.session.add(src)
            db.session.commit()

        piece = InformationPiece(
            report_id=report_id,
            source_id=src.id,
            category_id=self.categories_cache[cat_name],
            relevance_score=score,
            source=source,
            content=content,
            snippet=snippet[:500],
            created_at=datetime.utcnow(),
            repetition_count=1
        )
        db.session.add(piece)
        return piece

# Singleton Instance
data_processing_engine = DataProcessingEngine()