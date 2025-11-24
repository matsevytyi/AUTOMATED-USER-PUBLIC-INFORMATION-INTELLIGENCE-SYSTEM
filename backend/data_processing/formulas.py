# backend/formulas.py
from typing import Tuple, Dict, Optional, List
from datetime import datetime
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein
from sentence_transformers import SentenceTransformer, util
import math

# Load sentence transformer once
_EMBEDDING_MODEL = None


def get_embedding_model(name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        _EMBEDDING_MODEL = SentenceTransformer(name)
    return _EMBEDDING_MODEL


# -------------------------
# Matching helpers
# -------------------------

def normalize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return " ".join(s.lower().strip().split())


def fuzzy_score(a: str, b: str) -> float:
    """0..1 fuzzy similarity (partial token-aware)."""
    if not a or not b:
        return 0.0
    return fuzz.partial_ratio(a, b) / 100.0


def semantic_score(a: str, b: str, model=None) -> float:
    """
    Cosine similarity in [0..1] range (negative values clamped to 0).
    """
    if not a or not b:
        return 0.0
    model = model or get_embedding_model()
    emb1 = model.encode(a, convert_to_tensor=True)
    emb2 = model.encode(b, convert_to_tensor=True)
    cos = util.cos_sim(emb1, emb2).item()
    return max(0.0, float(cos))


def combined_match(a: str, b: str,
                   fuzzy_threshold: float = 0.75,
                   semantic_threshold: float = 0.80,
                   model=None) -> Tuple[bool, Dict[str, float]]:
    """
    Return (triggered_bool, {'fuzzy':..., 'semantic':...})
    triggered if fuzzy >= fuzzy_threshold OR semantic >= semantic_threshold.
    """
    a_n = normalize_text(a)
    b_n = normalize_text(b)
    f = fuzzy_score(a_n, b_n)
    s = semantic_score(a_n, b_n, model=model)
    triggered = (f >= fuzzy_threshold) or (s >= semantic_threshold)
    return triggered, {"fuzzy": f, "semantic": s}

