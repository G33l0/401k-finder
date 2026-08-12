import unittest
from unittest.mock import patch, MagicMock
from app.ein import find_ein

class TestEINDiscovery(unittest.TestCase):
    @patch('app.ein.get_connection')
    def test_exact_match_returns_high_confidence(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'ein': '123456789', 'name': 'Airgas USA, LLC'}
        ]
        mock_conn.return_value.execute.return_value = mock_cursor
        candidates = find_ein("Airgas USA, LLC")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['ein'], '123456789')
        self.assertGreater(candidates[0]['confidence'], 95)

    @patch('app.ein.get_connection')
    def test_no_match_returns_empty(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.return_value.execute.return_value = mock_cursor
        candidates = find_ein("Nonexistent Corp")
        self.assertEqual(len(candidates), 0)

    @patch('app.ein.get_connection')
    def test_token_match_medium_confidence(self, mock_conn):
        # Simulate token-based matching with multiple rows
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [
            [],  # exact match returns empty
            [{'ein': '987654321', 'name': 'Broulims Supermarkets Inc'}]  # token match
        ]
        mock_conn.return_value.execute.return_value = mock_cursor
        candidates = find_ein("Broulim's Supermarkets")
        self.assertGreater(len(candidates), 0)

if __name__ == '__main__':
    unittest.main()