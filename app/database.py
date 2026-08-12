import sqlite3
import os
from app.config import load_config

DB_PATH = None

def get_db_path():
    global DB_PATH
    if DB_PATH is None:
        config = load_config()
        DB_PATH = config['database_path']
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return DB_PATH

def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()
    # Existing tables (unchanged)
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        ein TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
    CREATE INDEX IF NOT EXISTS idx_companies_normalized ON companies(normalized_name);
    CREATE INDEX IF NOT EXISTS idx_companies_ein ON companies(ein);

    CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY,
        company_id INTEGER,
        plan_name TEXT,
        plan_number TEXT,
        plan_type TEXT,
        plan_year INTEGER,
        ein TEXT,
        filing_id TEXT UNIQUE,
        dataset_year INTEGER,
        FOREIGN KEY(company_id) REFERENCES companies(id)
    );
    CREATE INDEX IF NOT EXISTS idx_plans_company ON plans(company_id);
    CREATE INDEX IF NOT EXISTS idx_plans_ein ON plans(ein);
    CREATE INDEX IF NOT EXISTS idx_plans_year ON plans(plan_year);
    CREATE INDEX IF NOT EXISTS idx_plans_filing ON plans(filing_id);

    CREATE TABLE IF NOT EXISTS service_providers (
        id INTEGER PRIMARY KEY,
        plan_id INTEGER,
        provider_name TEXT,             -- exact name from filing
        provider_ein TEXT,
        service_codes TEXT,
        compensation REAL,
        classification TEXT,
        FOREIGN KEY(plan_id) REFERENCES plans(id)
    );
    CREATE INDEX IF NOT EXISTS idx_sp_plan ON service_providers(plan_id);

    CREATE TABLE IF NOT EXISTS provider_directory (
        id INTEGER PRIMARY KEY,
        legal_name TEXT NOT NULL,
        display_name TEXT,
        domain TEXT,
        homepage_url TEXT,
        login_url TEXT,
        phone TEXT,
        provider_type TEXT,
        recordkeeper BOOLEAN DEFAULT 0,
        last_verified TEXT,
        verification_source TEXT,
        active BOOLEAN DEFAULT 1
    );
    CREATE INDEX IF NOT EXISTS idx_provider_name ON provider_directory(legal_name);

    -- NEW TABLES for provider identity & temporal resolution
    CREATE TABLE IF NOT EXISTS provider_identities (
        id INTEGER PRIMARY KEY,
        canonical_name TEXT NOT NULL UNIQUE,
        current_display_name TEXT,
        current_legal_name TEXT,
        current_domain TEXT,
        provider_type TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS provider_aliases (
        id INTEGER PRIMARY KEY,
        provider_identity_id INTEGER NOT NULL,
        alias_name TEXT NOT NULL,
        alias_type TEXT NOT NULL CHECK(alias_type IN ('LEGAL_ENTITY','BRAND','TRADE_NAME',
            'FORM_5500_NAME','FORM_5500_SCHEDULE_NAME','HISTORICAL_NAME','ACQUIRED_COMPANY',
            'FORMER_NAME','PARENT_COMPANY','SUBSIDIARY','RECORDKEEPER_NAME','OTHER')),
        effective_start TEXT,
        effective_end TEXT,
        confidence REAL DEFAULT 1.0,
        source TEXT,
        source_url TEXT,
        FOREIGN KEY(provider_identity_id) REFERENCES provider_identities(id)
    );
    CREATE INDEX IF NOT EXISTS idx_aliases_identity ON provider_aliases(provider_identity_id);
    CREATE INDEX IF NOT EXISTS idx_aliases_name ON provider_aliases(alias_name);

    CREATE TABLE IF NOT EXISTS provider_name_history (
        id INTEGER PRIMARY KEY,
        provider_identity_id INTEGER NOT NULL,
        historical_name TEXT NOT NULL,
        valid_from TEXT,
        valid_to TEXT,
        source TEXT,
        source_url TEXT,
        confidence REAL DEFAULT 0.9,
        notes TEXT,
        FOREIGN KEY(provider_identity_id) REFERENCES provider_identities(id)
    );
    CREATE INDEX IF NOT EXISTS idx_name_history_identity ON provider_name_history(provider_identity_id);

    CREATE TABLE IF NOT EXISTS provider_relationships (
        id INTEGER PRIMARY KEY,
        from_identity_id INTEGER NOT NULL,
        to_identity_id INTEGER NOT NULL,
        relationship_type TEXT NOT NULL CHECK(relationship_type IN ('acquisition','rebrand','merger',
            'parent_subsidiary','same_entity','other')),
        effective_date TEXT,
        confidence REAL DEFAULT 0.9,
        source TEXT,
        source_url TEXT,
        notes TEXT,
        FOREIGN KEY(from_identity_id) REFERENCES provider_identities(id),
        FOREIGN KEY(to_identity_id) REFERENCES provider_identities(id)
    );

    -- Track individual dataset files downloaded
    CREATE TABLE IF NOT EXISTS dataset_files (
        id INTEGER PRIMARY KEY,
        dataset_year INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        file_type TEXT,               -- 'main', 'schedule_c', etc.
        compressed_size INTEGER,
        extracted_size INTEGER,
        checksum TEXT,
        download_date TEXT,
        source_url TEXT,
        processed BOOLEAN DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS dataset_versions (
        year INTEGER PRIMARY KEY,
        download_date TEXT,
        source_url TEXT,
        file_size INTEGER,
        checksum TEXT,
        record_count INTEGER,
        schema_version TEXT
    );

    CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT,
        year INTEGER,
        result_json TEXT,
        searched_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    # Also link provider_directory to identities (optional but not enforced as FK to allow flexibility)
    conn.execute("PRAGMA table_info(provider_directory)")
    cols = [row[1] for row in conn.fetchall()]
    if 'provider_identity_id' not in cols:
        conn.execute("ALTER TABLE provider_directory ADD COLUMN provider_identity_id INTEGER REFERENCES provider_identities(id)")
    conn.commit()
    conn.close()