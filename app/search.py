from app.ein import find_ein
from app.plans import is_401k_plan
from app.models import search_provider_directory
from app.database import get_connection
from app.confidence import calculate_confidence
from app.provider_resolution import resolve_provider

def perform_search(company, year):
    result = {
        'company': company,
        'year': year,
        'ein': None,
        'plan': None,
        'recordkeeper_filing_name': None,
        'recordkeeper_identity': None,
        'recordkeeper_current': None,
        'confidence': {},
        'evidence': []
    }
    ein_candidates = find_ein(company)
    if not ein_candidates:
        result['error'] = "Company not found in database."
        return result
    ein = ein_candidates[0]['ein']
    result['ein'] = ein
    result['evidence'].append('EIN match via DOL Form 5500')

    conn = get_connection()
    plans = conn.execute("SELECT * FROM plans WHERE ein=? AND plan_year=?", (ein, year)).fetchall()
    if not plans:
        plans = conn.execute("SELECT * FROM plans WHERE ein=? ORDER BY plan_year DESC LIMIT 1", (ein,)).fetchall()
        if plans:
            result['fallback_year'] = plans[0]['plan_year']
            result['evidence'].append(f"Requested year {year} not available; using latest filing {plans[0]['plan_year']}")
        else:
            result['error'] = "No plans found for this employer."
            return result

    k_plans = [p for p in plans if is_401k_plan(p['plan_name'])]
    if not k_plans:
        result['plan'] = plans[0]['plan_name']
        result['error'] = "No 401(k) plan identified; may be other retirement plan."
        return result

    plan = k_plans[0]
    result['plan'] = plan['plan_name']
    result['plan_number'] = plan['plan_number']

    providers = conn.execute("SELECT * FROM service_providers WHERE plan_id=?", (plan['id'],)).fetchall()
    recordkeepers = [p for p in providers if p['classification'] == 'RECORDKEEPER']
    if recordkeepers:
        rk = recordkeepers[0]
        result['recordkeeper_filing_name'] = rk['provider_name']
        # Resolve identity
        identity_info = resolve_provider(rk['provider_name'], year, rk.get('provider_ein'))
        result['recordkeeper_identity'] = identity_info['canonical_identity']
        result['recordkeeper_current'] = identity_info['current_name']
        result['evidence'].extend(identity_info['evidence'])
        # Overall confidence
        result['confidence'] = {
            'provider_match': identity_info['confidence'] * 100,
            'overall': calculate_confidence('HIGH')
        }
        # Provider directory lookup for login
        dir_entries = search_provider_directory(identity_info['canonical_identity'])
        if dir_entries:
            entry = dir_entries[0]
            result['provider_login_url'] = entry['login_url']
            result['provider_website'] = entry['homepage_url']
            result['provider_phone'] = entry['phone']
    else:
        result['recordkeeper_filing_name'] = "Recordkeeper could not be conclusively determined."
        result['confidence'] = {'overall': calculate_confidence('LOW')}

    return result