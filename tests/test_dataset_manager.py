import unittest
from unittest.mock import patch, MagicMock
from app.datasets import download_and_process_package, check_disk_space, calculate_package_sizes

class TestDatasetManager(unittest.TestCase):
    @patch('app.datasets.download_file')
    @patch('app.datasets.validate_zip_integrity', return_value=True)
    @patch('app.datasets.process_extracted_files')
    @patch('app.datasets.fetch_dataset_catalog')
    @patch('app.datasets.get_free_disk_space')
    def test_download_essential(self, mock_disk, mock_catalog, mock_process, mock_validate, mock_dl):
        # Mock catalog with one file of type main_form5500 and schedule_c
        mock_catalog.return_value = {
            2025: [("f_5500.zip", "http://dol.gov/2025-5500.zip", 5000000),
                   ("sch_c.zip", "http://dol.gov/2025-schc.zip", 2000000)]
        }
        mock_disk.return_value = 500_000_000  # plenty of space
        # Mock classify_file_type to return appropriate types
        with patch('app.datasets.classify_file_type', side_effect=['main_form5500', 'schedule_c']):
            download_and_process_package(2025, 'essential')
            self.assertTrue(mock_dl.called)
            self.assertEqual(mock_dl.call_count, 2)

    @patch('app.datasets.get_free_disk_space', return_value=1024)  # only 1KB free
    @patch('app.datasets.fetch_dataset_catalog')
    def test_insufficient_disk_raises(self, mock_catalog, mock_disk):
        mock_catalog.return_value = {2025: [("f.zip", "http://dol.gov/2025.zip", 5000000)]}
        with patch('app.datasets.classify_file_type', return_value='main_form5500'):
            with self.assertRaises(RuntimeError) as ctx:
                download_and_process_package(2025, 'essential')
            self.assertIn("Insufficient disk", str(ctx.exception))

if __name__ == '__main__':
    unittest.main()