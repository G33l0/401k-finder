import unittest
from unittest.mock import patch, MagicMock
from app.search import perform_search

class TestSearchPipeline(unittest.TestCase):
    @patch('app.search.find_ein')
    @patch('app.search.get_connection')
    @patch('app.search.is_401k_plan')
    @patch('app.search.resolve_provider')
    def test_successful_search(self, mock_resolve, mock_401k, mock_conn, mock_ein):
        # Setup mocks
        mock_ein.return_value = [{'ein': '123456789', 'confidence': 98}]
        # Mock database cursor for plans and providers
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [
            # plans query
            [{'id': 1, 'plan_name': 'Test 401k Plan', 'plan_number': '001', 'ein': '123456789', 'plan_year': 2025}],
            # service providers
            [{'id': 10, 'provider_name': 'Fidelity', 'provider_ein': '987654321', 'service_codes': '50', 'compensation': 1000, 'classification': 'RECORDKEEPER'}]
        ]
        mock_conn.return_value.execute.return_value = mock_cursor
        mock_401k.return_value = True
        mock_resolve.return_value = {
            'filing_name': 'Fidelity', 'canonical_identity': 'Fidelity Investments', 'current_name': 'Fidelity', 'confidence': 0.95
        }

        result = perform_search("ACME", 2025)
        self.assertEqual(result['ein'], '123456789')
        self.assertEqual(result['plan'], 'Test 401k Plan')
        self.assertEqual(result['recordkeeper_filing_name'], 'Fidelity')
        self.assertEqual(result['recordkeeper_identity'], 'Fidelity Investments')

    @patch('app.search.find_ein')
    def test_no_company_found(self, mock_ein):
        mock_ein.return_value = []
        result = perform_search("Ghost", 2025)
        self.assertIn('error', result)

if __name__ == '__main__':
    unittest.main()