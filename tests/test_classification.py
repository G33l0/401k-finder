import unittest
from app.classification import classify_provider

class TestProviderClassification(unittest.TestCase):
    def test_recordkeeper_identification(self):
        self.assertEqual(classify_provider("Fidelity Investments", "Recordkeeping and administration"), 'RECORDKEEPER')
        self.assertEqual(classify_provider("Empower Retirement", "Daily valuation"), 'RECORDKEEPER')

    def test_trustee_custodian(self):
        self.assertEqual(classify_provider("Trust Co", "Trustee services"), 'TRUSTEE')
        self.assertEqual(classify_provider("Custodian Bank", "Custodian"), 'CUSTODIAN')

    def test_tpa(self):
        self.assertEqual(classify_provider("Third Party Admin LLC", "TPA services"), 'TPA')

    def test_investment_manager(self):
        self.assertEqual(classify_provider("Vanguard Group", "Investment management"), 'INVESTMENT_MANAGER')
        self.assertEqual(classify_provider("BlackRock", "Investment advisory"), 'INVESTMENT_MANAGER')

    def test_auditor(self):
        self.assertEqual(classify_provider("Ernst & Young", "Audit"), 'AUDITOR')

    def test_other(self):
        self.assertEqual(classify_provider("Random Payroll", "Payroll processing"), 'OTHER')
        self.assertEqual(classify_provider("", ""), 'OTHER')

if __name__ == '__main__':
    unittest.main()