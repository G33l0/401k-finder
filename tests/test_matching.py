import unittest
from app.utils import normalize_company_name
from app.matching import exact_match, token_similarity, fuzzy_similarity

class TestCompanyNameNormalization(unittest.TestCase):
    def test_llc_variations(self):
        self.assertEqual(normalize_company_name("Airgas USA, LLC"), "AIRGAS USA")
        self.assertEqual(normalize_company_name("Airgas USA LLC"), "AIRGAS USA")
        self.assertEqual(normalize_company_name("AIRGAS USA L.L.C."), "AIRGAS USA")

    def test_inc_variations(self):
        self.assertEqual(normalize_company_name("Acme Inc."), "ACME")
        self.assertEqual(normalize_company_name("ACME INC"), "ACME")
        self.assertEqual(normalize_company_name("Acme, Inc."), "ACME")

    def test_punctuation_and_spacing(self):
        self.assertEqual(normalize_company_name("The  Sample   Company,  ltd."), "THE SAMPLE COMPANY")
        self.assertEqual(normalize_company_name("!@# Test & Co."), "TEST CO")

    def test_empty_and_none(self):
        self.assertEqual(normalize_company_name(""), "")
        self.assertEqual(normalize_company_name(None), "")

class TestExactMatch(unittest.TestCase):
    def test_exact_normalized_match(self):
        self.assertTrue(exact_match("Airgas USA, LLC", "Airgas USA LLC"))
        self.assertTrue(exact_match("ACME Inc.", "ACME INC"))

    def test_different_companies(self):
        self.assertFalse(exact_match("Airgas USA, LLC", "Broulim's Supermarkets"))

class TestTokenSimilarity(unittest.TestCase):
    def test_high_similarity(self):
        sim = token_similarity("Airgas USA LLC", "Airgas USA")
        self.assertGreater(sim, 0.8)

    def test_low_similarity(self):
        sim = token_similarity("Airgas USA LLC", "ACME Corp")
        self.assertLess(sim, 0.3)

class TestFuzzySimilarity(unittest.TestCase):
    def test_fuzzy_match(self):
        sim = fuzzy_similarity("Airgas USA", "Airgas USA, LLC")
        self.assertGreater(sim, 0.9)

    def test_fuzzy_different(self):
        sim = fuzzy_similarity("Airgas", "Microsoft")
        self.assertLess(sim, 0.5)

if __name__ == '__main__':
    unittest.main()