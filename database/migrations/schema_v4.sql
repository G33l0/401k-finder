CREATE TABLE evidence (
	id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	filing_id INTEGER, 
	party_id INTEGER, 
	form_year INTEGER NOT NULL, 
	ack_id VARCHAR(40), 
	source_type VARCHAR(60) NOT NULL, 
	dataset VARCHAR(60), 
	schedule_code VARCHAR(20), 
	source_file VARCHAR(500), 
	source_row INTEGER, 
	field_name VARCHAR(120), 
	field_value TEXT, 
	notes TEXT, 
	confidence VARCHAR(10), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_evidence_source_field UNIQUE (ack_id, dataset, source_row, field_name), 
	FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE, 
	FOREIGN KEY(filing_id) REFERENCES filings (id) ON DELETE CASCADE, 
	FOREIGN KEY(party_id) REFERENCES plan_parties (id) ON DELETE CASCADE
);

CREATE TABLE filings (
	id INTEGER NOT NULL, 
	ack_id VARCHAR(40) NOT NULL, 
	plan_id INTEGER NOT NULL, 
	form_year INTEGER NOT NULL, 
	form_type VARCHAR(20) NOT NULL, 
	plan_name VARCHAR(500), 
	sponsor_name VARCHAR(500), 
	ein VARCHAR(9), 
	plan_number VARCHAR(3), 
	plan_year_begin DATE, 
	plan_year_end DATE, 
	filing_status VARCHAR(60), 
	date_received DATE, 
	is_initial BOOLEAN, 
	is_amended BOOLEAN, 
	is_final BOOLEAN, 
	is_short_year BOOLEAN, 
	plan_entity_code VARCHAR(2), 
	dfe_entity_code VARCHAR(2), 
	business_code VARCHAR(6), 
	pension_codes VARCHAR(200), 
	welfare_codes VARCHAR(200), 
	plan_category VARCHAR(30), 
	plan_features VARCHAR(400), 
	total_participants INTEGER, 
	active_participants INTEGER, 
	participants_with_balances INTEGER, 
	total_assets_boy FLOAT, 
	total_assets_eoy FLOAT, 
	net_assets_eoy FLOAT, 
	employer_contributions FLOAT, 
	participant_contributions FLOAT, 
	admin_name VARCHAR(200), 
	admin_ein VARCHAR(9), 
	source_dataset VARCHAR(60), 
	source_release VARCHAR(20), 
	source_file VARCHAR(500), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE
);

CREATE TABLE imported_datasets (
	id INTEGER NOT NULL, 
	form_year INTEGER NOT NULL, 
	dataset VARCHAR(60) NOT NULL, 
	release VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	source_url VARCHAR(1000), 
	source_file VARCHAR(500), 
	file_sha256 VARCHAR(64), 
	file_size INTEGER, 
	rows_read INTEGER NOT NULL, 
	rows_imported INTEGER NOT NULL, 
	rows_skipped INTEGER NOT NULL, 
	parties_created INTEGER NOT NULL, 
	error TEXT, 
	started_at DATETIME, 
	finished_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_import_year_dataset_release UNIQUE (form_year, dataset, release)
);

CREATE VIRTUAL TABLE plan_fts USING fts5(
            plan_name,
            sponsor_name,
            sponsor_dba_name,
            ein UNINDEXED,
            plan_number UNINDEXED,
            sponsor_city,
            sponsor_state,
            plan_id UNINDEXED,
            tokenize = "unicode61 remove_diacritics 2"
        );

CREATE TABLE 'plan_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;

CREATE TABLE 'plan_fts_content'(id INTEGER PRIMARY KEY, c0, c1, c2, c3, c4, c5, c6, c7);

CREATE TABLE 'plan_fts_data'(id INTEGER PRIMARY KEY, block BLOB);

CREATE TABLE 'plan_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);

CREATE TABLE 'plan_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;

CREATE TABLE plan_parties (
	id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	provider_id INTEGER NOT NULL, 
	filing_id INTEGER, 
	role VARCHAR(60) NOT NULL, 
	reported_name VARCHAR(500), 
	reported_ein VARCHAR(9), 
	relationship_text VARCHAR(200), 
	form_year INTEGER NOT NULL, 
	schedule_code VARCHAR(20), 
	source_field VARCHAR(120), 
	service_codes VARCHAR(120), 
	direct_compensation FLOAT, 
	indirect_compensation FLOAT, 
	confidence VARCHAR(10), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_party_plan_provider_role_year UNIQUE (plan_id, provider_id, role, form_year, schedule_code), 
	FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE, 
	FOREIGN KEY(provider_id) REFERENCES providers (id) ON DELETE CASCADE, 
	FOREIGN KEY(filing_id) REFERENCES filings (id) ON DELETE CASCADE
);

CREATE TABLE plans (
	id INTEGER NOT NULL, 
	ein VARCHAR(9), 
	plan_number VARCHAR(3), 
	plan_name VARCHAR(500) NOT NULL, 
	sponsor_name VARCHAR(500), 
	sponsor_dba_name VARCHAR(500), 
	sponsor_city VARCHAR(200), 
	sponsor_state VARCHAR(2), 
	sponsor_zip VARCHAR(12), 
	sponsor_phone VARCHAR(30), 
	business_code VARCHAR(6), 
	plan_effective_date DATE, 
	plan_category VARCHAR(30), 
	plan_features VARCHAR(400), 
	benefit_codes VARCHAR(200), 
	is_retirement_plan BOOLEAN NOT NULL, 
	first_year INTEGER, 
	last_year INTEGER, 
	latest_participants INTEGER, 
	latest_active_participants INTEGER, 
	latest_total_assets FLOAT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_plan_ein_pn UNIQUE (ein, plan_number)
);

CREATE VIRTUAL TABLE provider_fts USING fts5(
            name,
            canonical_name,
            provider_id UNINDEXED,
            tokenize = "unicode61 remove_diacritics 2"
        );

CREATE TABLE 'provider_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;

CREATE TABLE 'provider_fts_content'(id INTEGER PRIMARY KEY, c0, c1, c2);

CREATE TABLE 'provider_fts_data'(id INTEGER PRIMARY KEY, block BLOB);

CREATE TABLE 'provider_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);

CREATE TABLE 'provider_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;

CREATE TABLE providers (
	id INTEGER NOT NULL, 
	name VARCHAR(500) NOT NULL, 
	name_key VARCHAR(500) NOT NULL, 
	ein VARCHAR(9), 
	city VARCHAR(200), 
	state VARCHAR(2), 
	canonical_name VARCHAR(200), 
	primary_role VARCHAR(60), 
	plan_count INTEGER NOT NULL, 
	participant_count INTEGER NOT NULL, 
	assets_under_administration FLOAT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE schedule_records (
	id INTEGER NOT NULL, 
	ack_id VARCHAR(40) NOT NULL, 
	plan_id INTEGER, 
	filing_id INTEGER, 
	form_year INTEGER NOT NULL, 
	dataset VARCHAR(60) NOT NULL, 
	schedule_code VARCHAR(20) NOT NULL, 
	row_order INTEGER, 
	source_file VARCHAR(500), 
	source_row INTEGER, 
	raw_data JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_schedule_ack_dataset_row UNIQUE (ack_id, dataset, row_order), 
	FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE, 
	FOREIGN KEY(filing_id) REFERENCES filings (id) ON DELETE CASCADE
);

CREATE TABLE schema_version ( version INTEGER NOT NULL, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);

CREATE INDEX ix_evidence_ack_id ON evidence (ack_id);

CREATE INDEX ix_evidence_filing_id ON evidence (filing_id);

CREATE INDEX ix_evidence_form_year ON evidence (form_year);

CREATE INDEX ix_evidence_party_id ON evidence (party_id);

CREATE INDEX ix_evidence_plan_id ON evidence (plan_id);

CREATE INDEX ix_evidence_plan_year ON evidence (plan_id, form_year);

CREATE INDEX ix_evidence_schedule_code ON evidence (schedule_code);

CREATE INDEX ix_filing_plan_year ON filings (plan_id, form_year);

CREATE INDEX ix_filing_year_type ON filings (form_year, form_type);

CREATE UNIQUE INDEX ix_filings_ack_id ON filings (ack_id);

CREATE INDEX ix_filings_ein ON filings (ein);

CREATE INDEX ix_filings_filing_status ON filings (filing_status);

CREATE INDEX ix_filings_form_type ON filings (form_type);

CREATE INDEX ix_filings_form_year ON filings (form_year);

CREATE INDEX ix_filings_plan_id ON filings (plan_id);

CREATE INDEX ix_imported_datasets_dataset ON imported_datasets (dataset);

CREATE INDEX ix_imported_datasets_form_year ON imported_datasets (form_year);

CREATE INDEX ix_imported_datasets_status ON imported_datasets (status);

CREATE INDEX ix_party_plan_year_role ON plan_parties (plan_id, form_year, role);

CREATE INDEX ix_party_provider_year ON plan_parties (provider_id, form_year);

CREATE INDEX ix_party_role_year ON plan_parties (role, form_year);

CREATE INDEX ix_plan_name_nocase ON plans (plan_name COLLATE NOCASE);

CREATE INDEX ix_plan_parties_filing_id ON plan_parties (filing_id);

CREATE INDEX ix_plan_parties_form_year ON plan_parties (form_year);

CREATE INDEX ix_plan_parties_plan_id ON plan_parties (plan_id);

CREATE INDEX ix_plan_parties_provider_id ON plan_parties (provider_id);

CREATE INDEX ix_plan_parties_role ON plan_parties (role);

CREATE INDEX ix_plan_parties_schedule_code ON plan_parties (schedule_code);

CREATE INDEX ix_plan_retirement_year ON plans (is_retirement_plan, last_year);

CREATE INDEX ix_plan_sponsor_nocase ON plans (sponsor_name COLLATE NOCASE);

CREATE INDEX ix_plan_sponsor_state ON plans (sponsor_name, sponsor_state);

CREATE INDEX ix_plans_business_code ON plans (business_code);

CREATE INDEX ix_plans_ein ON plans (ein);

CREATE INDEX ix_plans_first_year ON plans (first_year);

CREATE INDEX ix_plans_is_retirement_plan ON plans (is_retirement_plan);

CREATE INDEX ix_plans_last_year ON plans (last_year);

CREATE INDEX ix_plans_latest_participants ON plans (latest_participants);

CREATE INDEX ix_plans_latest_total_assets ON plans (latest_total_assets);

CREATE INDEX ix_plans_plan_category ON plans (plan_category);

CREATE INDEX ix_plans_plan_features ON plans (plan_features);

CREATE INDEX ix_plans_plan_name ON plans (plan_name);

CREATE INDEX ix_plans_plan_number ON plans (plan_number);

CREATE INDEX ix_plans_sponsor_name ON plans (sponsor_name);

CREATE INDEX ix_plans_sponsor_state ON plans (sponsor_state);

CREATE INDEX ix_plans_sponsor_zip ON plans (sponsor_zip);

CREATE INDEX ix_provider_name_nocase ON providers (name COLLATE NOCASE);

CREATE INDEX ix_providers_canonical_name ON providers (canonical_name);

CREATE INDEX ix_providers_ein ON providers (ein);

CREATE INDEX ix_providers_name ON providers (name);

CREATE UNIQUE INDEX ix_providers_name_key ON providers (name_key);

CREATE INDEX ix_providers_plan_count ON providers (plan_count);

CREATE INDEX ix_providers_primary_role ON providers (primary_role);

CREATE INDEX ix_providers_state ON providers (state);

CREATE INDEX ix_schedule_records_ack_id ON schedule_records (ack_id);

CREATE INDEX ix_schedule_records_dataset ON schedule_records (dataset);

CREATE INDEX ix_schedule_records_filing_id ON schedule_records (filing_id);

CREATE INDEX ix_schedule_records_form_year ON schedule_records (form_year);

CREATE INDEX ix_schedule_records_plan_id ON schedule_records (plan_id);

CREATE INDEX ix_schedule_records_schedule_code ON schedule_records (schedule_code);

CREATE INDEX ix_schedule_year_dataset ON schedule_records (form_year, dataset);

CREATE UNIQUE INDEX uq_evidence_source_field
        ON evidence (ack_id, dataset, source_row, field_name)
        ;
