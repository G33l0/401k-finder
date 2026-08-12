import unittest
from unittest.mock import patch, MagicMock
from app.datasets import fetch_dataset_catalog, get_latest_year, calculate_package_sizes

class TestDatasetCatalog(unittest.TestCase):
    @patch('app.datasets.urllib.request.urlopen')
    def test_fetch_catalog_parses_years(self, mock_urlopen):
        # Simulate HTML response with links to datasets
        html = b"""
        <html>
        <a href="https://www.dol.gov/sites/dolgov/files/ebsa/.../2025-5500-sf-private-pension-plan.zip">2025 Form 5500</a>
        <a href="https://www.dol.gov/sites/dolgov/files/ebsa/.../2025-5500-sch-c.zip">2025 Schedule C (12.5 MB)</a>
        <a href="https://www.dol.gov/sites/dolgov/files/ebsa/.../2024-5500-sf-private-pension-plan.zip">2024 Form 5500</a>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value.read.return_value = html
        mock_urlopen.return_value = mock_resp
        catalog = fetch_dataset_catalog()
        self.assertIn(2025, catalog)
        self.assertIn(2024, catalog)
        files = catalog[2025]
        self.assertEqual(len(files), 2)
        # Check size extraction for second file
        _, _, size = files[1]
        self.assertIsNotNone(size)
        self.assertAlmostEqual(size, 12.5 * 1024 * 1024, delta=1000)

    def test_get_latest_year(self):
        catalog = {2023: [], 2024: [], 2025: []}
        self.assertEqual(get_latest_year(catalog), 2025)

    def test_package_size_calculation(self):
        catalog = {
            2025: [
                ("file1.zip", "http://example.com/1", 10*1024*1024),  # 10 MB compressed
                ("file2.zip", "http://example.com/2", 5*1024*1024),
            ]
        }
        # Mock classify_file_type to return 'main_form5500' and 'schedule_c'
        with patch('app.datasets.classify_file_type', side_effect=['main_form5500', 'schedule_c']):
            sizes = calculate_package_sizes(catalog, 2025, 'essential')
            self.assertEqual(sizes['compressed'], 15*1024*1024)
            # extracted = compressed * expansion factor (8.0 default)
            self.assertAlmostEqual(sizes['extracted'], 15*8*1024*1024, delta=1000)
            self.assertEqual(len(sizes['file_list']), 2)

if __name__ == '__main__':
    unittest.main()