import unittest
from app.plans import is_401k_plan

class TestPlanIdentification(unittest.TestCase):
    def test_recognize_401k_keywords(self):
        self.assertTrue(is_401k_plan("401(k) Retirement Savings Plan"))
        self.assertTrue(is_401k_plan("401K PROFIT SHARING PLAN"))
        self.assertTrue(is_401k_plan("Employee Savings Plan"))
        self.assertTrue(is_401k_plan("Defined Contribution Plan"))

    def test_non_401k_plan(self):
        self.assertFalse(is_401k_plan("Defined Benefit Pension Plan"))
        self.assertFalse(is_401k_plan("Health and Welfare Plan"))
        self.assertFalse(is_401k_plan("ESOP"))
        self.assertFalse(is_401k_plan(""))

    def test_plan_with_401k_in_description(self):
        self.assertTrue(is_401k_plan("My Company 401(k) and Profit Sharing Plan"))

if __name__ == '__main__':
    unittest.main()