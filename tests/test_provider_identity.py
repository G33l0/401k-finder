import unittest
import tempfile
import os
import sqlite3
from app.database import initialize_database, get_db_path
from app.models import (create_provider_identity, add_provider_alias, add_provider_name_history,
                        get_provider_identity_by_name)
from app.provider_resolution import resolve_provider

class TestProviderIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use in-memory DB for testing
        os.environ['TESTING'] = '1'
        # Override DB path
        from app import database
        database.DB_PATH = ':memory:'
        initialize_database()

    def test_add_identity(self):
        id1 = create_provider_identity("Empower", "Empower Retirement")
        self.assertIsNotNone(id1)

    def test_alias_resolution(self):
        id1 = create_provider_identity("Empower")
        add_provider_alias(id1, "Great-West Life & Annuity", "FORM_5500_NAME")
        result = resolve_provider("Great-West Life & Annuity")
        self.assertEqual(result['canonical_identity'], "Empower")
        self.assertGreater(result['confidence'], 0.9)

    def test_history_resolution(self):
        id1 = create_provider_identity("Empower")
        add_provider_name_history(id1, "Great-West", "2019-01-01", "2020-12-31")
        result = resolve_provider("Great-West")
        self.assertEqual(result['canonical_identity'], "Empower")

    def test_unknown_provider(self):
        result = resolve_provider("Random Unknown Co")
        self.assertIsNone(result['canonical_identity'])
        self.assertEqual(result['confidence'], 0.0)

if __name__ == '__main__':
    unittest.main()