import math
from datetime import datetime, timezone
from sqlalchemy import func
from backend.models import InformationPiece, InformationCategory, Report

class RiskAssessmentEngine:
    """
    Implements the Risk Assessment model described in Part 3.4.
    Flow: Context Relevance -> Word Risk -> Validation -> Recency -> Impact -> Total Risk.
    """

    # Constants
    ALPHA = 0.7  # Weighting factor for relevance
    LAMBDA_DECAY = 0.15  # Decay constant for recency
    EPSILON = 1e-9  # Prevent division by zero

    IMPACT_SCORES = {
        "Financial Information": 1.0,
        "Personal Identifiers": 1.0,
        "Contact Information": 0.9,
        "Location Data": 0.9,
        "Social Connections": 0.5,
        "Professional Details": 0.5,
        "Public Statements": 0.5,
        "Uncategorized": 0.5
    }

    RISK_KEYWORDS = [
        # Status
        'breach', 'leaked', 'exposed', 'compromised', 'hacked', 'pwned', 'dump',
        # Credentials
        'password', 'secret', 'credential', 'token', 'api_key', 'private_key', 'admin', 'root', 'login',
        # Confidentiality
        'confidential', 'restricted', 'sensitive', 'private', 'internal_use'
    ]

    def __init__(self, db):
        self.db = db

    def process_risk_assessment(self, information_pieces: list, current_query_text: str) -> tuple:
        """
        Main pipeline processing a list of InformationPiece objects.
        Returns: (processed_pieces, risk_values_list)
        """
        risk_values = []
        processed = []
        
        # Cache category names for performance
        cat_map = {c.id: c.name for c in self.db.session.query(InformationCategory).all()}

        for piece in information_pieces:
            
            # 1. Relevance Score (Context + Word-based)
            s_relevance = self._calculate_relevance(piece)
            
            # 2. Validation Score (Corroboration)
            s_validation = self._calculate_validation(piece, current_query_text=current_query_text)
            
            # 3. Recency Score (Time Decay)
            s_recency = self._calculate_recency(piece)
            
            # 4. Likelihood Calculation
            # Formula: (S_rel + S_val + S_rec) / 3
            r_likelihood = (s_relevance + s_validation + s_recency) / 3.0
            
            # 5. Impact Score
            cat_name = cat_map.get(piece.category_id, "Uncategorized")
            r_impact = self.IMPACT_SCORES.get(cat_name, 0.5)
            
            # 6. Total Risk Calculation
            # Formula: R_impact * R_likelihood * 10
            r_total = r_impact * r_likelihood * 10.0
            
            # Clamp to (0, 10] range
            r_total = max(0.1, min(r_total, 10.0))
            
            print(f"ID: {piece.content}, Relevance: {s_relevance:.2f}, Validation: {s_validation:.2f}, Recency: {s_recency:.2f}, Likelihood: {r_likelihood:.2f}, Impact: {r_impact:.2f}, Total Risk: {r_total:.2f}")
            
            # Update Object
            piece.risk_score = r_total
            piece.risk_level = self._get_label(r_total)
            
            risk_values.append(r_total)
            processed.append(piece)
            
        return processed, risk_values

    def _calculate_relevance(self, piece) -> float:
        """
        S_relevance = (1 - alpha) * S_word + alpha * CosineSimilarity
        """
        # S_word: 1 if containing flag words, 0 otherwise
        text = (piece.content or "") + " " + (piece.snippet or "")
        text_lower = text.lower()
        
        s_word = 0.0
        if any(w in text_lower for w in self.RISK_KEYWORDS):
            s_word = 1.0
            
        # Cosine Similarity is to be pre-calculated in 'relevance_score' during Data Processing (Vector Embedding step). Default to 0.5 if missing.
        cosine_sim = piece.relevance_score if piece.relevance_score is not None else 0.5
        
        return (1 - self.ALPHA) * s_word + self.ALPHA * cosine_sim

    def _calculate_validation(self, piece, current_query_text) -> float:
        """
        S_validation = Sum(W_supporting) / (Sum(W_supporting) + Sum(W_contradicting) + epsilon)
        """
        
        sum_w_supporting = self.db.session.query(InformationPiece)\
            .join(Report, InformationPiece.report_id == Report.report_id)\
            .filter(InformationPiece.content == piece.content)\
            .filter(Report.user_query == current_query_text)\
            .count()
            
        sum_w_supporting += 1
        
        sum_w_contradicting = self.db.session.query(InformationPiece)\
            .join(Report, InformationPiece.report_id == Report.report_id)\
            .filter(InformationPiece.content == piece.content)\
            .filter(Report.user_query != current_query_text)\
            .count()
            
        print("query: ", current_query_text, "sum_w_supporting: ", sum_w_supporting, "sum_w_contradicting: ", sum_w_contradicting)
        
        return sum_w_supporting / (sum_w_supporting + sum_w_contradicting + self.EPSILON)

    def _calculate_recency(self, piece) -> float:
        """
        S_recency = e^(-lambda * T_diff)
        """
        if not piece.created_at:
            return 0.5
            
        # Calculate months elapsed
        current_query_text = piece.report.user_query

        earliest_occurrence = self.db.session.query(InformationPiece)\
            .join(Report, InformationPiece.report_id == Report.report_id)\
            .filter(InformationPiece.content == piece.content)\
            .filter(Report.user_query == current_query_text)\
            .order_by(InformationPiece.created_at.asc())\
            .first()
            
        if earliest_occurrence:
            earliest_date = earliest_occurrence.created_at
        else:
            # If nothing found in DB (unlikely if 'piece' is saved), use current
            earliest_date = piece.created_at
            
        now = datetime.now(timezone.utc).replace(tzinfo=None) 
        delta = now - earliest_date

        t_diff = delta.days / 30.0
        
        return math.exp(-self.LAMBDA_DECAY * t_diff)

    def _get_label(self, score):
        if score >= 7.0: return "high"
        if score >= 4.0: return "medium"
        return "low"