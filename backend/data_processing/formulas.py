# backend/formulas.py
from typing import Tuple, Dict, Optional, List
from datetime import datetime
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein
from sentence_transformers import SentenceTransformer, util
import math

from backend.utils.config import Config

semantic_model = SentenceTransformer(Config.SEMANTIC_MODEL)


# -------------------------
# Matching helpers
# -------------------------

def normalize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return " ".join(s.lower().strip().split())


def levenstain_score(a: str, b: str) -> float:
    """0..1 levenstain similarity (partial token-aware)."""
    if not a or not b:
        return 0.0
    return fuzz.partial_ratio(a, b) / 100.0


def semantic_score(a: str, b: str, model=None) -> float:
    """
    Cosine similarity in [0..1] range (negative values clamped to 0).
    """
    if not a or not b:
        return 0.0
    model = model or semantic_model
    emb1 = model.encode(a, convert_to_tensor=True)
    emb2 = model.encode(b, convert_to_tensor=True)
    cos = util.cos_sim(emb1, emb2).item()
    return max(0.0, float(cos))


def combined_match(a: str, b: str,
                   levenstain_threshold: float = Config.LEVENSTAIN_THRESHOLD,
                   semantic_threshold: float = Config.SEMANTIC_THRESHOLD,
                   model=None) -> Tuple[bool, Dict[str, float]]:
    """
    Return (triggered_bool, {'levenstain':..., 'semantic':...})
    triggered if levenstain >= levenstain_threshold OR semantic >= semantic_threshold.
    """
    a_n = normalize_text(a)
    b_n = normalize_text(b)
    f = levenstain_score(a_n, b_n)
    s = semantic_score(a_n, b_n, model=model)
    triggered = (f >= levenstain_threshold) or (s >= semantic_threshold)
    return triggered, {"levenstain": f, "semantic": s}

# -------------------------
# Relevance score (4.5.3.3)
# -------------------------


def name_match_score(target_name: str, candidate_name: str) -> float:
    """
    Use Levenshtein similarity normalized to [0..1].
    We will compute ratio = 1 - (lev_dist / max_len)
    """
    if not target_name or not candidate_name:
        return 0.0
    a = normalize_text(target_name)
    b = normalize_text(candidate_name)
    dist = levenstain_score(a, b)
    return dist


def context_match_score(context_a: str, context_b: str, model=None) -> float:
    """Cosine similarity of embeddings (0..1)."""
    return semantic_score(context_a, context_b, model=model)


def total_relevance_score(user_query: str,
                          extracted_content: str,
                          extracted_context: str,
                          alpha: float = Config.NAME_COEFFICIENT,
                          beta: float = Config.CONTEXT_COEFFICIENT,
                          model=None) -> float:
    """
    Compute Total Relevance Score = α*Name + β*Context
    alpha+beta  must be ~1 (we don't enforce but recommended)
    Returns value in [0..1].
    """
    # normalize weights
    s = alpha + beta
    if s == 0:
        alpha, beta = Config.NAME_COEFFICIENT, Config.CONTEXT_COEFFICIENT
    else:
        alpha, beta = alpha / s, beta / s

    nm = name_match_score(user_query, extracted_content)
    ctx = context_match_score(user_query, extracted_context, model=model)

    total = alpha * nm + beta * ctx
    return max(0.0, min(1.0, total))

# -------------------------
# Temporal Risk Adjustment (4.5.3.4)
# -------------------------

def recency_factor(published_at: Optional[datetime], now: Optional[datetime] = None) -> float:
    """
    Returns RecencyFactor = max(0, 1 - days_since_publication/365)
    If published_at is None -> treat as old -> 0
    """
    if not published_at:
        return 0.0
    now = now or datetime.utcnow()
    days = (now - published_at).days
    rf = max(0.0, 1.0 - days / 365.0)
    return rf


def adjusted_risk_score(base_risk_score: float, published_at: Optional[datetime]) -> float:
    """
    Adjusted Risk Score = base_risk_score * (1 + RecencyFactor)
    base_risk_score expected in [0..10] range 
    """
    rf = recency_factor(published_at)
    return base_risk_score * (1.0 + rf)


# -------------------------
# Overall Risk Score (4.5.3.1)
# -------------------------

def overall_risk_score(r_scores: List[float], weights: List[float]) -> float:
    """
    r_scores: list of risk scores r_i (scale 1-10)
    weights: list of weights w_i (category weights)
    returns weighted average (or 0 if sum weights 0)
    """
    if not r_scores or not weights or len(r_scores) != len(weights):
        return 0.0
    num = sum([r * w for r, w in zip(r_scores, weights)])
    den = sum(weights) or 1.0
    return num / den

def calculate_validation_score(corroborating_count, contradictory_count) -> float:
    """
    Calculate validation score for an InformationPiece .
    """
    
    total_count = (corroborating_count - contradictory_count + 1) / ( corroborating_count + contradictory_count + 2)
    if total_count < 1:
        return 1.0
    
    return total_count


# -------------------------
# Information Change Calculation (4.5.3.5)
# -------------------------

def change_score(new_count: int, modified_count: int, total_old_count: int) -> float:
    """
    Change Score = (New + Modified) / Total_old * 100%
    If total_old_count == 0 -> return 100% if new_count>0 else 0.
    """
    if total_old_count <= 0:
        return 100.0 if new_count > 0 else 0.0
    return (new_count + modified_count) / total_old_count * 100.0


# -------------------------
# Exposure Breadth (4.5.3.6)
# -------------------------

def exposure_breadth(num_distinct_sources: int, total_sources_scanned: int) -> float:
    if total_sources_scanned <= 0:
        return 0.0
    return (num_distinct_sources / total_sources_scanned) * 100.0