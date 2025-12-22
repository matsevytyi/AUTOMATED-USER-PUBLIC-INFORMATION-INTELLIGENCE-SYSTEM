import re
from datetime import datetime, timedelta
from transformers import pipeline
from sentence_transformers import SentenceTransformer, util
from rapidfuzz import fuzz


from backend.models import InformationPiece, InformationCategory, DiscoverSource, User, SearchHistory
from backend.utils.config import Config


class DataProcessingEngine:
    """
    Singleton engine for Data Processing.
    Handles Normalization, NER, Regex, Validation, and Canonization.
    """
    _instance = None

    DENY_LIST = {
        'linkedin', 'facebook', 'instagram', 'twitter', 'google', 
        'tiktok', 'youtube', 'social media', 'profile', 'posts'
    }

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DataProcessingEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db):
        if self._initialized:
            return
            
        print("[INIT] Loading NER Model...")
        self.ner_pipeline = pipeline("ner", model=Config.NER_MODEL, grouped_entities=True)
        
        print("[INIT] Loading Semantic Model...")
        self.semantic_model = SentenceTransformer(Config.SEMANTIC_MODEL)
        
        self.db = db
        
        self.categories_cache = {}
        self._initialized = True
        
        
    # =============== Public API ===============

    def process_raw_data(self, data_list, report_id, report_query, db):
        """
        Main pipeline entry point corresponding to DFD Level 2.
        """
        processed_pieces = []
        
        # dictionary {canonized_key: piece_object} for intelligent merging
        # key format: "Category:LowerCaseContent"
        local_cache = {} 
        
        # 1. Normalization
        clean_entries = self._normalize_inputs(data_list)

        for entry in clean_entries:
            text = entry['text']
            source = entry['source']
            
            # 2. Entity Extraction (NER + Regex)
            # Returns list of dicts: {'word': str, 'category': str, 'start': int, 'end': int}
            candidates = self._extract_candidates(text)
            
            for candidate in candidates:
                val_text = candidate['word']
                cat_type = candidate['category']
                method = candidate['method']
                
                # 3. Validation & Cleaning
                # Fix "Harlequin DefenseWe" -> "Harlequin Defense We"
                val_text = self._clean_glued_words(val_text)
                
                # Fix "##edIn" artifacts manually
                val_text = val_text.replace("##", "")

                if not self._validate_rules(val_text, report_query, cat_type):
                    continue
                
                # 4. Canonization (Standardize format)
                # "LITHUANIA" -> "Lithuania"
                final_text = self._canonize(val_text, cat_type)
                
                # 5. Merge & Deduplicate
                # check if a similar entity already exists in this batch
                merge_key = f"{cat_type}:{final_text.lower()}"
                
                if merge_key in local_cache:
                    # Already exists: just increment occurrence or update metadata
                    existing_piece = local_cache[merge_key]
                    existing_piece.repetition_count += 1
                    # If the new text is "better" (e.g. title case vs upper case), update it
                    if final_text[0].isupper() and not existing_piece.content[0].isupper():
                        existing_piece.content = final_text
                    continue
                if method == 'NER':
                    # Check for substrings (Harlequin Defense vs Harlequin DefenseWe)
                    
                    if self._validate_entity_specificity(final_text, cat_type):
                        continue
                    
                    found_fuzzy = False
                    for key, existing_piece in local_cache.items():
                        existing_cat = key.split(':')[0]
                        if existing_cat != cat_type: continue
                        
                        # one is contained in the other and difference is short
                        s1 = final_text.lower()
                        s2 = existing_piece.content.lower()
                        
                        if (s1 in s2 or s2 in s1) and abs(len(s1) - len(s2)) < 4:
                            # merge into the shorter/cleaner one 
                            target_piece = existing_piece if len(s2) <= len(s1) else None
                            
                            if target_piece:
                                target_piece.repetition_count += 1
                                found_fuzzy = True
                                break
                            
                    if found_fuzzy:
                        continue

                # 6. Vector Embedding
                similarity = self._calculate_context_relevance(content=final_text, snippet=text, user_query=report_query)
                
                # Create and Cache
                piece = self._create_information_piece(
                    db, final_text, cat_type, source, report_id, similarity, text
                )
                local_cache[merge_key] = piece
                processed_pieces.append(piece)
                
        db.session.commit()
        return processed_pieces
    
    # detect misusers (on user request)
    def get_local_misuse_score(self, user_id, current_query):
        user = self.db.session.query(User).get(user_id)
        if not user: return 0.0
        
        u1 = (user.name or "").lower().strip()
        u2 = (user.email.split('@')[0] if user.email else "").lower().strip()
        
        # extract Entities
        ner_results = self.ner_pipeline(current_query, grouped_entities=True)
        r_words = re.findall(r'\b[A-Z][a-z]+\b', current_query)
        ignored = {'Report', 'Search', 'Find', 'Who', 'Where', 'When', 'The'}
        
        # refine and canonize
        candidates = {}
        for ent in ner_results:
            if ent['entity_group'] == 'PER':
                candidates[ent['word'].replace("##", "").strip()] = True
        for word in r_words:
            if word not in ignored:
                ner_results_2 = self.ner_pipeline(word, grouped_entities=True)
                if len(ner_results_2) > 0 and ner_results_2[0].get('entity_group'):
                    if ner_results_2[0]['entity_group'] == 'PER':
                            candidates[ent['word'].replace("##", "").strip()] = True

        if not candidates:
            return 0.0

        ratios = []
        for val_text in candidates.keys():
            v_low = val_text.lower()
            
            # Immediate Substring Match
            # If "Andrii" is in "Andrii Matsevytyi" -> 0.0 misuse
            if (u1 and (v_low in u1 or u1 in v_low)) or (u2 and (v_low in u2 or u2 in v_low)):
                ratios.append(0.0)
                ratios.append(0.0)
                continue
                
            # Token Sort Ratio (Handles Name Swaps) 
            # "Matsevytyi Andrii" vs "Andrii Matsevytyi" will score ~100
            sim1 = fuzz.token_sort_ratio(u1, v_low) / 100.0 if u1 else 0
            sim2 = fuzz.token_sort_ratio(u2, v_low) / 100.0 if u2 else 0
            
            # Token Set Ratio (Handles partial/nicknames)
            # Useful if user.name is "Andrii Matsevytyi" but search is just "Andrii"
            set_sim1 = fuzz.token_set_ratio(u1, v_low) / 100.0 if u1 else 0
            set_sim2 = fuzz.token_set_ratio(u2, v_low) / 100.0 if u2 else 0
            
            best_sim = max(sim1, sim2, set_sim1, set_sim2)
            
            print(f"MISUSE CHECK: '{val_text}' vs '{u1}' | Score: {1.0 - best_sim:.2f}")
            ratios.append(1.0 - best_sim)
        
        if not ratios:
            return 0.0

        local_score = sum(ratios) / len(ratios)

        return min(1.0, max(0.0, local_score))
    
    # =============== Helper Functions ===============

    def _normalize_inputs(self, data):
        normalized = []
        def clean(s):
            s = re.sub(r'["\'`«»]', '', s) 
            s = re.sub(r'\s+', ' ', s)
            return s.strip()

        for item in data:
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
        candidates = [] 
        
        # A. NER Extraction
        try:
            # 1. Raw NER
            ner_results = self.ner_pipeline(text, grouped_entities=True) 
            ner_results.sort(key=lambda x: x['start'])

            # 2. Merge Adjacent Persons
            merged_results = []
            if ner_results:
                curr = ner_results[0]
                
                for next_ent in ner_results[1:]:
                    
                    gap = text[curr['end']:next_ent['start']]

                    if (curr['entity_group'] == 'PER' and next_ent['entity_group'] == 'PER' and 
                        gap in ['', ' ', '-']):
                        
                        # Combine words: e.g. "Vytautas" + " " + "Rudžionis"
                        curr['word'] += gap + next_ent['word']
                        curr['end'] = next_ent['end']
                        curr['score'] = (curr['score'] + next_ent['score']) / 2
                    else:
                        # No merge, push current and move to next
                        merged_results.append(curr)
                        curr = next_ent
                
                # Append the last one
                merged_results.append(curr)

            # 3.Extend Text
            for entity in merged_results:
                word = entity['word']
                group = entity['entity_group']
                end_pos = entity['end']
                
                #  Check for cut-off words
                suffix = text[end_pos:]
                
                #  matches continuous letters at the start of the suffix
                continuation_match = re.match(r'^([a-zа-яёіїє]+)', suffix)
                
                if continuation_match:
                    extension = continuation_match.group(1)
                    # print(f"[DEBUG] Extending '{word}' with '{extension}'")
                    word += extension
                
                if group == 'PER': cat = 'Social Connections'
                elif group == 'ORG': cat = 'Professional Details'
                elif group == 'LOC': cat = 'Location Data'
                else: cat = 'Uncategorized'
                
                candidates.append({'word': word, 'category': cat, 'method': 'NER'})
        except Exception:
            pass

        # B. Regex Extraction
         # 2. Emails
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
        candidates.extend([{'word': email, 'category': 'Contact Information', 'method': 'REGEX'} for email in emails])
        
        # 3. Financial info (keywords or patterns like $1000, UAH, etc.)
        financial = re.findall(r'\$\d+(?:,\d{3})*(?:\.\d{2})?|\b(?:UAH|EUR|USD|грн|долар|євро|euro|buck|dollar|$|€|£)\b', text)
        candidates.extend([{'word': fin, 'category': 'Financial Information', 'method': 'REGEX'} for fin in financial])

        # 4. Phone numbers (with extended cases support)
        phones = re.findall(r'(?<!\d)(?:\+?\d{1,3}[ -]?)?\(?\d{2,3}\)?[ -]?\d{3}[ -]?\d{2,4}(?!\d)', text)
        candidates.extend([{'word': m, 'category': 'Contact Information', 'method': 'REGEX'} for m in phones])

        # 5. Social media (usernames or links)
        social = re.findall(r' @\S+', text)
        candidates.extend([{'word': item, 'category': 'Contact Information', 'method': 'REGEX'} for item in social])
        
        # 6. Professional titles (simple keyword match)
        professions = ['CEO', 'founder', 'developer', 'manager', 'engineer', 'analyst', 'specialist', 'student']
        for prof in professions:
            if re.search(r'\b' + re.escape(prof) + r'\b', text, re.IGNORECASE):
                candidates.append({'word': prof, 'category': 'Professional Details', 'method': 'REGEX'})

        # 7. Public statements (e.g., quotes or keywords like "said", "tweeted")
        if re.search(r'\b(said|stated|tweeted|posted|commented)\b', text, re.IGNORECASE):
            candidates.append({'word': 'Public Statement', 'category': 'Public Statement', 'method': 'REGEX'})

        # 8. Other personal identifiers (passport, ID, etc. — extend as needed)
        identifiers = re.findall(r'\bID[:\s]*\d+|passport[:\s]*\w+\d+', text, re.IGNORECASE)
        candidates.extend([{'word': id_val, 'category': 'Personal Identifiers', 'method': 'REGEX'} for id_val in identifiers])

        return candidates

    def _validate_rules(self, text, query, category):
        # 1. Min length
        if len(text) < 3: return False
        
        # 2. Deny List (LinkedIn, Facebook, etc.)
        if text.lower() in self.DENY_LIST: return False

        # 3. Check for Dates masquerading as Phones
        if category == 'Contact Information':
            # If it matches YYYY-MM-DD pattern
            if re.search(r'\d{4}-\d{2}-\d{2}', text): return False
            # If it's mostly 0s or small numbers
            if text.strip() == "0": return False

        # 4. Input Query Check (Rotation & Split)
        if query:
            q_lower = query.lower()
            t_lower = text.lower()
            
            # A. Exact substring check
            if t_lower in q_lower or q_lower in t_lower:
                return False
                
            # B. Token subset check (Rotation check)
            # If entity is "Andrii Matsev" and query is "Matsevytyi Andrii"
            # We break both into sets of words/subwords and check overlap
            q_tokens = set(re.findall(r'\w+', q_lower))
            t_tokens = set(re.findall(r'\w+', t_lower))
            
            # If all significant tokens of the text are in the query, it's not new info
            # e.g. text="Andrii", query="Andrii Matsevytyi" -> Skip
            if t_tokens.issubset(q_tokens):
                return False
                
            # C. Fuzzy Check
            ratio = fuzz.ratio(t_lower, q_lower)
            if ratio > 85: return False
                
        return True

    def _clean_glued_words(self, text):
        """
        Removes a final glued Capitalized word.
        Examples:
        - 'HarlequinWe' -> 'Harlequin'
        - 'Harlequin DefenseAp' -> 'Harlequin Defense'
        """
        
        return re.sub(r'[A-Z][a-z]*$', '', text).strip()

    def _canonize(self, text, category):
        """Standardize format."""
        text = text.strip()
        

        if category in ['Social Connections', 'Location Data', 'Professional Details']:
            text = text.title()

        if category == 'Contact Information':
            # Clean phones
            if any(c.isdigit() for c in text) and '@' not in text:
                return re.sub(r'[\s\-\(\)]', '', text)
                
        return text

    def _validate_entity_specificity(self, text: str, category: str) -> float:
        """
        (a) Specificity Score: Determines if an extracted entry is a specific named entity 
        (e.g., 'Vilnius University') or a generic category label (e.g., 'University').
        
        Technique: Differential Similarity
        Returns: Float between 0.0 (Generic/Noise) and 1.0 (Specific/Valid)
        """
        # Define pairs: (Positive/Specific Ref, Negative/General Ref)
        refs = {
            'Social Connections': (
                'A specific personal name, username, or social media handle', 
                'A generic reference to a person or people'
            ),
            'Professional Details': (
                'A specific organization name, company, or institution', 
                'A general business concept or job title'
            ),
            'Location Data': (
                'A specific geographic location, city, or address', 
                'A general direction or spatial concept'
            ),
            'Contact Information': (
                'A specific email, phone number, or digital contact', 
                'The general concept of communication'
            ),
            'Financial Information': (
                'A specific price, account number, or currency value', 
                'The general concept of money'
            )
        }
        
        # Default to a neutral check if category is unknown
        pos_ref, neg_ref = refs.get(category, ('A specific named entity', 'A general category or noise'))

        # Encode all inputs
        emb_text = self.semantic_model.encode(text, convert_to_tensor=True)
        emb_pos = self.semantic_model.encode(pos_ref, convert_to_tensor=True)
        emb_neg = self.semantic_model.encode(neg_ref, convert_to_tensor=True)

        # Calculate distances
        similarity_to_specific = float(util.cos_sim(emb_text, emb_pos).item())
        similarity_to_general = float(util.cos_sim(emb_text, emb_neg).item())

        
        # Penalty: subtract similarity to general term
        if similarity_to_general > similarity_to_specific:
            return False

        return True

    def _calculate_context_relevance(self, content: str, snippet: str, user_query: str) -> float:
        """
        (b) Context Relevance Score: Evaluates if the context (snippet) actively supports 
        the exploitation of the content (entry) relative to the specific User.
        
        Technique: Weighted Contextual Attribution vs. Noise Filtering
        """
        if not snippet:
            return 0.5  # Neutral fallback if no context

        # 1. Define Reference Phrases for Intent
        # Positive: The context confirms this info belongs to the target user
        attribution_refs = [f"{content} belongs to {user_query} or author",
                           f"{content} is related to {user_query} or author",
                           f"{content} is about {user_query} or author",
                           f"{content} is from {user_query} or author",
                           f"{content} is by {user_query} or author",
                           ]
        
        # Negative 1: The context indicates this belongs to a third party/scammer
        exclusion_refs = [f"{content} does not belong to {user_query} or author",
                         f"{content} is not related to {user_query} or author",
                         f"{content} is not about {user_query} or author",
                         f"{content} is not from {user_query} or author",
                         f"{content} is not by {user_query} or author",
                         f"{content} has nothing to do with {user_query} or author",
                         ]
        
        # Negative 2: The context is just website navigation/noise
        noise_ref = "Website menu footer copyright contact us home page"
        
        attribution_embs = []
        exclusion_embs = []
        
        attribution_scores = []
        exclusion_scores = []

        # 2. Encode Inputs
        emb_snippet = self.semantic_model.encode(snippet, convert_to_tensor=True)
        for attribution_ref in attribution_refs:
            attribution_embs.append(self.semantic_model.encode(attribution_ref, convert_to_tensor=True))
        for exclusion_ref in exclusion_refs:
            exclusion_embs.append(self.semantic_model.encode(exclusion_ref, convert_to_tensor=True))

        emb_noise = self.semantic_model.encode(noise_ref, convert_to_tensor=True)

        # 3. Calculate Similarities
        for emb_attr in attribution_embs:
            attribution_scores.append(float(util.cos_sim(emb_snippet, emb_attr).item()))
            
        for emb_excl in exclusion_embs:
            exclusion_scores.append(float(util.cos_sim(emb_snippet, emb_excl).item()))
        
        score_attribution = max(attribution_scores)
        if '@' in content: score_attribution += 0.2

        score_exclusion = max(exclusion_scores)
        score_noise = float(util.cos_sim(emb_snippet, emb_noise).item())

        # 4. Weighted Scoring Logic
        if score_attribution > score_exclusion: 
            final_score = 1.0
        else:
            final_score = score_attribution
        
        # Apply penalties
        if score_noise > 0.6:
            final_score *= 0.5 
        

        # boost if extracted content is textually present in snippet
        if content.lower() in snippet.lower():
            final_score += 0.1

        return max(0.0, min(final_score, 1.0))

    def _create_information_piece(self, db, content, cat_name, source, report_id, score, snippet):
        # Resolve Category
        if cat_name not in self.categories_cache:
            cat = db.session.query(InformationCategory).filter_by(name=cat_name).first()
            if not cat:
                cat = InformationCategory(name=cat_name, weight=0.5)
                db.session.add(cat)
                db.session.commit()
            self.categories_cache[cat_name] = cat.id
            
        # Resolve Source
        discovered_from = "Social Media" if "facebook.com" in (source or "") else "Web Data"
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
from models import db
data_processing_engine = DataProcessingEngine(db)