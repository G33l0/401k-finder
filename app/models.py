from app.database import get_connection

# ... existing functions for companies, plans, service_providers, provider_directory ...
# (unchanged, but I'll show them for completeness)
def insert_company(name, normalized, ein=None):
    conn = get_connection()
    cur = conn.execute("INSERT OR IGNORE INTO companies (name, normalized_name, ein) VALUES (?,?,?)",
                       (name, normalized, ein))
    conn.commit()
    return cur.lastrowid

def get_company_by_ein(ein):
    conn = get_connection()
    return conn.execute("SELECT * FROM companies WHERE ein=?", (ein,)).fetchone()

def insert_plan(company_id, plan_name, plan_number, plan_type, plan_year, ein, filing_id, dataset_year):
    conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO plans (company_id, plan_name, plan_number, plan_type, plan_year, ein, filing_id, dataset_year) VALUES (?,?,?,?,?,?,?,?)",
                 (company_id, plan_name, plan_number, plan_type, plan_year, ein, filing_id, dataset_year))
    conn.commit()

def insert_service_provider(plan_id, provider_name, provider_ein, service_codes, compensation, classification):
    conn = get_connection()
    conn.execute("INSERT INTO service_providers (plan_id, provider_name, provider_ein, service_codes, compensation, classification) VALUES (?,?,?,?,?,?)",
                 (plan_id, provider_name, provider_ein, service_codes, compensation, classification))
    conn.commit()

# Provider directory (linked to identity)
def add_provider_directory(data):
    conn = get_connection()
    conn.execute("""INSERT INTO provider_directory (legal_name, display_name, domain, homepage_url, login_url, phone,
                    provider_type, recordkeeper, last_verified, verification_source, active, provider_identity_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                 (data['legal_name'], data.get('display_name'), data.get('domain'),
                  data.get('homepage_url'), data.get('login_url'), data.get('phone'),
                  data.get('provider_type'), data.get('recordkeeper', 0),
                  data.get('last_verified'), data.get('verification_source'),
                  data.get('active', 1), data.get('provider_identity_id')))
    conn.commit()

def search_provider_directory(name):
    conn = get_connection()
    return conn.execute("SELECT * FROM provider_directory WHERE legal_name LIKE ? OR display_name LIKE ?",
                        (f'%{name}%', f'%{name}%')).fetchall()

# ---------- NEW: Provider Identity management ----------
def create_provider_identity(canonical_name, current_display_name=None, current_legal_name=None, current_domain=None, provider_type=None):
    conn = get_connection()
    cur = conn.execute("""INSERT INTO provider_identities (canonical_name, current_display_name, current_legal_name, current_domain, provider_type)
                          VALUES (?,?,?,?,?)""",
                       (canonical_name, current_display_name, current_legal_name, current_domain, provider_type))
    conn.commit()
    return cur.lastrowid

def get_provider_identity_by_name(name):
    conn = get_connection()
    # Search in canonical_name, aliases, history
    identity = conn.execute("SELECT * FROM provider_identities WHERE canonical_name LIKE ?", (f'%{name}%',)).fetchone()
    if not identity:
        # try aliases
        alias = conn.execute("SELECT provider_identity_id FROM provider_aliases WHERE alias_name LIKE ?", (f'%{name}%',)).fetchone()
        if alias:
            identity = conn.execute("SELECT * FROM provider_identities WHERE id=?", (alias['provider_identity_id'],)).fetchone()
    if not identity:
        # try name history
        hist = conn.execute("SELECT provider_identity_id FROM provider_name_history WHERE historical_name LIKE ?", (f'%{name}%',)).fetchone()
        if hist:
            identity = conn.execute("SELECT * FROM provider_identities WHERE id=?", (hist['provider_identity_id'],)).fetchone()
    return identity

def add_provider_alias(identity_id, alias_name, alias_type, effective_start=None, effective_end=None, confidence=1.0, source=None, source_url=None):
    conn = get_connection()
    conn.execute("""INSERT INTO provider_aliases (provider_identity_id, alias_name, alias_type, effective_start, effective_end, confidence, source, source_url)
                    VALUES (?,?,?,?,?,?,?,?)""",
                 (identity_id, alias_name, alias_type, effective_start, effective_end, confidence, source, source_url))
    conn.commit()

def add_provider_name_history(identity_id, historical_name, valid_from=None, valid_to=None, source=None, source_url=None, confidence=0.9):
    conn = get_connection()
    conn.execute("""INSERT INTO provider_name_history (provider_identity_id, historical_name, valid_from, valid_to, source, source_url, confidence)
                    VALUES (?,?,?,?,?,?,?)""",
                 (identity_id, historical_name, valid_from, valid_to, source, source_url, confidence))
    conn.commit()

def add_provider_relationship(from_id, to_id, relationship_type, effective_date=None, confidence=0.9, source=None, source_url=None):
    conn = get_connection()
    conn.execute("""INSERT INTO provider_relationships (from_identity_id, to_identity_id, relationship_type, effective_date, confidence, source, source_url)
                    VALUES (?,?,?,?,?,?,?)""",
                 (from_id, to_id, relationship_type, effective_date, confidence, source, source_url))
    conn.commit()

# Dataset file tracking
def record_dataset_file(year, file_name, file_type, compressed_size=None, extracted_size=None, checksum=None, source_url=None):
    conn = get_connection()
    conn.execute("""INSERT INTO dataset_files (dataset_year, file_name, file_type, compressed_size, extracted_size, checksum, source_url, download_date)
                    VALUES (?,?,?,?,?,?,?, datetime('now'))""",
                 (year, file_name, file_type, compressed_size, extracted_size, checksum, source_url))
    conn.commit()

def get_dataset_files(year):
    conn = get_connection()
    return conn.execute("SELECT * FROM dataset_files WHERE dataset_year=?", (year,)).fetchall()