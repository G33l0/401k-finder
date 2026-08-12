from app.database import get_connection
from app.utils import normalize_company_name
from app.matching import token_similarity
import logging

logger = logging.getLogger(__name__)

def find_ein(company_name, year=None):
    """Search for EIN candidates by company name."""
    conn = get_connection()
    normalized = normalize_company_name(company_name)
    # Exact match
    rows = conn.execute("SELECT * FROM companies WHERE normalized_name = ?", (normalized,)).fetchall()
    if rows:
        return [{'ein': r['ein'], 'confidence': 98} for r in rows if r['ein']]
    # Token match
    tokens = normalized.split()
    candidates = {}
    for token in tokens:
        cur = conn.execute("SELECT * FROM companies WHERE normalized_name LIKE ?", (f'%{token}%',))
        for r in cur:
            sim = token_similarity(company_name, r['name'])
            if sim > 0.7:
                candidates.setdefault(r['ein'], sim)
    if candidates:
        best = max(candidates, key=candidates.get)
        return [{'ein': best, 'confidence': int(candidates[best]*100)}]
    return []