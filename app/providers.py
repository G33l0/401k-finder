from app.models import (create_provider_identity, add_provider_alias, add_provider_name_history,
                        add_provider_relationship, search_provider_directory, get_provider_identity_by_name)
from app.utils import is_valid_url

def add_full_provider(canonical, current_display=None, current_legal=None, domain=None, login_url=None, phone=None, aliases=None, history=None):
    """Add a provider identity with optional aliases and history."""
    if login_url and not is_valid_url(login_url):
        raise ValueError("Invalid login URL")
    identity_id = create_provider_identity(canonical, current_display, current_legal, domain)
    # Add directory entry linked to identity
    from app.models import add_provider_directory
    add_provider_directory({
        'legal_name': canonical,
        'display_name': current_display or canonical,
        'domain': domain,
        'homepage_url': f"https://{domain}" if domain else None,
        'login_url': login_url,
        'phone': phone,
        'provider_type': 'recordkeeper',
        'recordkeeper': 1,
        'provider_identity_id': identity_id
    })
    if aliases:
        for alias_name, alias_type in aliases:
            add_provider_alias(identity_id, alias_name, alias_type)
    if history:
        for hist_name, valid_from, valid_to in history:
            add_provider_name_history(identity_id, hist_name, valid_from, valid_to)
    return identity_id