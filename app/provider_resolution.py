from app.database import get_connection
from app.utils import normalize_provider_name
import logging

logger = logging.getLogger(__name__)

def resolve_provider(provider_name, year=None, provider_ein=None):
    """
    Given a raw provider name (as appears in filing), return resolved identity info.
    Returns a dict with:
        filing_name: original
        canonical_identity: canonical provider name
        current_name: current display name (if known)
        identity_id: database ID of provider_identities
        relationship: description of transition (if any)
        confidence: 0-1
        evidence: list of strings
    """
    result = {
        'filing_name': provider_name,
        'canonical_identity': None,
        'current_name': None,
        'identity_id': None,
        'relationship': None,
        'confidence': 0.0,
        'evidence': []
    }
    conn = get_connection()
    norm_name = normalize_provider_name(provider_name)
    # 1. Direct match by canonical name (exact or normalized)
    identity = conn.execute("SELECT * FROM provider_identities WHERE canonical_name=?", (provider_name.strip(),)).fetchone()
    if not identity:
        identity = conn.execute("SELECT * FROM provider_identities WHERE canonical_name LIKE ?", (f'%{norm_name}%',)).fetchone()
    # 2. Check aliases
    if not identity:
        alias = conn.execute("""SELECT pi.* FROM provider_aliases pa
                                JOIN provider_identities pi ON pa.provider_identity_id = pi.id
                                WHERE pa.alias_name = ? OR pa.alias_name LIKE ?""",
                             (provider_name.strip(), f'%{norm_name}%')).fetchone()
        if alias:
            identity = alias
            result['evidence'].append('Matched via provider alias')
    # 3. Check name history
    if not identity:
        hist = conn.execute("""SELECT pi.* FROM provider_name_history pnh
                               JOIN provider_identities pi ON pnh.provider_identity_id = pi.id
                               WHERE pnh.historical_name = ? OR pnh.historical_name LIKE ?""",
                            (provider_name.strip(), f'%{norm_name}%')).fetchone()
        if hist:
            identity = hist
            result['evidence'].append('Matched via historical name')
    if not identity:
        result['confidence'] = 0.0
        result['evidence'].append('No identity match found')
        return result

    result['identity_id'] = identity['id']
    result['canonical_identity'] = identity['canonical_name']
    result['current_name'] = identity['current_display_name'] or identity['canonical_name']
    result['confidence'] = 0.95  # high confidence for exact match
    # Determine relationship if provider_name differs from canonical
    if provider_name.strip().lower() != identity['canonical_name'].strip().lower():
        # Check relationships
        rel = conn.execute("""SELECT * FROM provider_relationships
                              WHERE (from_identity_id=? AND relationship_type IN ('acquisition','rebrand','merger'))
                              OR (to_identity_id=?)""",
                           (identity['id'], identity['id'])).fetchone()
        if rel:
            result['relationship'] = f"{provider_name} → {identity['canonical_name']}"
            result['evidence'].append(f"Relationship: {rel['relationship_type']}")
        else:
            result['relationship'] = f"Name variation of {identity['canonical_name']}"
    return result