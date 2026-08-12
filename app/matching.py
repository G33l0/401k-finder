from difflib import SequenceMatcher
from app.utils import normalize_company_name

def exact_match(name1, name2):
    return normalize_company_name(name1) == normalize_company_name(name2)

def token_similarity(name1, name2):
    set1 = set(normalize_company_name(name1).split())
    set2 = set(normalize_company_name(name2).split())
    if not set1 or not set2:
        return 0
    intersection = set1 & set2
    return len(intersection) / max(len(set1), len(set2))

def fuzzy_similarity(name1, name2):
    return SequenceMatcher(None, normalize_company_name(name1), normalize_company_name(name2)).ratio()