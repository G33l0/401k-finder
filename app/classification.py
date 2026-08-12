import re

KNOWN_RECORDKEEPERS = [
    'fidelity', 'vanguard', 'empower', 't. rowe price', 'principal', 'voya',
    'transamerica', 'nationwide', 'lincoln financial', 'charles schwab', 'merrill',
    'john hancock', 'tiaa', 'massmutual', 'the standard', 'oneamerica', 'ascensus',
    'newport', 'alight', 'human interest', 'guideline', 'paychex', 'adp',
]

def classify_provider(name, service_codes, row=None):
    """Classify provider into RECORDKEEPER, TPA, CUSTODIAN, etc."""
    name_lower = name.lower() if name else ''
    codes = service_codes or ''
    # Heuristic based on known names
    for rk in KNOWN_RECORDKEEPERS:
        if rk in name_lower:
            # Distinguish recordkeeper from other roles if service codes indicate
            if 'recordkeep' in codes.lower() or 'administration' in codes.lower() or 'daily valuation' in codes.lower():
                return 'RECORDKEEPER'
    # Fallback: if service codes contain 'CUSTODIAN'
    if 'custodian' in codes.lower() or 'trustee' in codes.lower():
        if 'trustee' in codes.lower():
            return 'TRUSTEE'
        return 'CUSTODIAN'
    if 'tpa' in codes.lower() or 'third party admin' in codes.lower():
        return 'TPA'
    if 'investment' in codes.lower() or 'adviser' in codes.lower():
        return 'INVESTMENT_MANAGER'
    if 'auditor' in codes.lower():
        return 'AUDITOR'
    return 'OTHER'