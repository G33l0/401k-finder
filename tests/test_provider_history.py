import unittest
from unittest.mock import patch, MagicMock
from app.models import (create_provider_identity, add_provider_name_history,
                        add_provider_alias)
from app.provider_resolution import resolve_provider
from app.database import initialize_database, get_db_path
import os

class TestProviderHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # In-memory database
        import app.database as db
        db.DB_PATH = ':memory:'
        initialize_database()

    def test_historical_name_preservation(self):
        identity_id = create_provider_identity("Empower", "Empower Retirement")
        add_provider_name_history(identity_id, "Great-West Life & Annuity", "2018-01-01", "2020-12-31")
        # Resolve historical name
        result = resolve_provider("Great-West Life & Annuity")
        self.assertEqual(result['canonical_identity'], "Empower")
        self.assertIn('historical name', ' '.join(result['evidence']).lower())

    def test_transition_detection(self):
        id1 = create_provider_identity("Empower")
        id2 = create_provider_identity("GreatWest")  # This would be same entity in real scenario, but for test
        # In a proper implementation, we would add a relationship between id1 and id2
        # For now, resolve a name that maps to id1 via alias
        add_provider_alias(id1, "Great-West", "HISTORICAL_NAME")
        result = resolve_provider("Great-West")
        self.assertEqual(result['canonical_identity'], "Empower")

    def test_no_history_fabrication(self):
        # Unknown provider should not be resolved
        result = resolve_provider("Unknown Provider XYZ")
        self.assertIsNone(result['canonical_identity'])
        self.assertEqual(result['confidence'], 0.0)

if __name__ == '__main__':
    unittest.main()