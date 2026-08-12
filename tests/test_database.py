import unittest
import os
import sqlite3
from app.database import initialize_database, get_connection, get_db_path

class TestDatabaseInitialization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use temporary file
        cls.temp_db = '/tmp/test_401k.db'
        # Override path
        import app.database as db
        db.DB_PATH = cls.temp_db
        initialize_database()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.temp_db):
            os.remove(cls.temp_db)

    def test_tables_exist(self):
        conn = get_connection()
        tables = ['companies', 'plans', 'service_providers', 'provider_directory',
                  'provider_identities', 'provider_aliases', 'provider_name_history',
                  'provider_relationships', 'dataset_files', 'dataset_versions', 'search_history', 'settings']
        for t in tables:
            cur = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{t}'")
            self.assertIsNotNone(cur.fetchone(), f"Table {t} missing")
        conn.close()

    def test_company_insert(self):
        from app.models import insert_company
        insert_company("Test Corp", "TEST CORP", "123456789")
        conn = get_connection()
        row = conn.execute("SELECT * FROM companies WHERE ein='123456789'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['name'], "Test Corp")

    def test_plan_insert(self):
        from app.models import insert_plan, insert_company
        cid = insert_company("PlanSponsor", "PLANSPONSOR", "111222333")
        insert_plan(cid, "Test Plan", "001", "2E", 2025, "111222333", "ACK_TEST", 2025)
        conn = get_connection()
        plan = conn.execute("SELECT * FROM plans WHERE filing_id='ACK_TEST'").fetchone()
        self.assertEqual(plan['plan_name'], "Test Plan")

if __name__ == '__main__':
    unittest.main()