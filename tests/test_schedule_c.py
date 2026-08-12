import unittest
from unittest.mock import patch, MagicMock
from app.schedule_c import parse_schedule_c

class TestScheduleCParsing(unittest.TestCase):
    @patch('app.schedule_c.insert_service_provider')
    @patch('app.schedule_c.classify_provider')
    def test_parse_valid_csv(self, mock_classify, mock_insert):
        mock_classify.return_value = 'RECORDKEEPER'
        # Create a temporary CSV content
        csv_content = "SPONSOR_EIN,PLAN_NUMBER,SERVICE_PROVIDER_NAME,SERVICE_PROVIDER_EIN,SERVICE_CODES,COMPENSATION\n"
        csv_content += "123456789,001,Fidelity Investments,987654321,50,15000\n"
        mock_file = MagicMock()
        mock_file.__iter__.return_value = csv_content.splitlines()
        # We'll patch built-in open
        with patch('builtins.open', return_value=mock_file), \
             patch('csv.DictReader', return_value=[
                 {'SPONSOR_EIN':'123456789','PLAN_NUMBER':'001','SERVICE_PROVIDER_NAME':'Fidelity Investments',
                  'SERVICE_PROVIDER_EIN':'987654321','SERVICE_CODES':'50','COMPENSATION':'15000'}
             ]):
            # Dummy plan mapping
            plan_map = {('123456789','001'): 1}
            parse_schedule_c('fake.csv', plan_map)
            mock_insert.assert_called_once_with(1, 'Fidelity Investments', '987654321', '50', '15000', 'RECORDKEEPER')

    @patch('app.schedule_c.insert_service_provider')
    def test_missing_columns_skips(self, mock_insert):
        # Simulate CSV without required columns
        with patch('builtins.open', side_effect=Exception("missing column")):
            plan_map = {}
            # Should not crash, and insert not called
            with self.assertRaises(Exception):
                parse_schedule_c('fake.csv', plan_map)
            mock_insert.assert_not_called()

if __name__ == '__main__':
    unittest.main()