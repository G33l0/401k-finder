import unittest
from main import parse_args

class TestCLIArgs(unittest.TestCase):
    def test_company_and_year(self):
        args = parse_args().parse_args(['--company', 'Airgas', '--year', '2025'])
        self.assertEqual(args.company, 'Airgas')
        self.assertEqual(args.year, 2025)

    def test_ein_flag(self):
        args = parse_args().parse_args(['--company', 'Airgas', '--ein'])
        self.assertTrue(args.ein)

    def test_history_flag(self):
        args = parse_args().parse_args(['--company', 'Airgas', '--history'])
        self.assertTrue(args.history)

    def test_provider_search(self):
        args = parse_args().parse_args(['--provider', 'Fidelity'])
        self.assertEqual(args.provider, 'Fidelity')

    def test_json_output(self):
        args = parse_args().parse_args(['--company', 'Test', '--json'])
        self.assertTrue(args.json)

    def test_health_check(self):
        args = parse_args().parse_args(['--health'])
        self.assertTrue(args.health)

    def test_update(self):
        args = parse_args().parse_args(['--update'])
        self.assertTrue(args.update)

    def test_self_test(self):
        args = parse_args().parse_args(['--self-test'])
        self.assertTrue(args.self_test)

if __name__ == '__main__':
    unittest.main()