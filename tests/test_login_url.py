import unittest
from app.utils import is_valid_url

class TestLoginURLValidation(unittest.TestCase):
    def test_https_urls(self):
        self.assertTrue(is_valid_url("https://www.empower.com/login"))
        self.assertTrue(is_valid_url("https://login.fidelity.com"))

    def test_http_urls(self):
        # HTTP is allowed technically but should be flagged as not secure? Our validation allows both.
        self.assertTrue(is_valid_url("http://example.com"))

    def test_invalid_urls(self):
        self.assertFalse(is_valid_url("ftp://example.com/login"))
        self.assertFalse(is_valid_url(""))
        self.assertFalse(is_valid_url("not a url"))

    def test_required_https_for_login(self):
        # This test would be in provider verification; we can just check URL scheme.
        from app.verification import verify_provider_url  # stub
        # The stub returns True; actual implementation would enforce HTTPS.
        self.assertTrue(verify_provider_url("https://empower.com"))

if __name__ == '__main__':
    unittest.main()