import sys, os
sys.path.insert(0, os.path.abspath("."))

import unittest
from backend.security.sanitizer import SensitiveDataSanitizer


class TestSensitiveDataSanitizer(unittest.TestCase):
    def test_sanitize_openai_and_anthropic_keys(self):
        text = "Configured with sk-1234567890abcdef12345678 and sk-ant-api03-abcdef1234567890abcdef."
        sanitized = SensitiveDataSanitizer.sanitize_text(text)
        self.assertNotIn("sk-1234567890abcdef12345678", sanitized)
        self.assertNotIn("sk-ant-api03-abcdef1234567890abcdef", sanitized)
        self.assertIn("[REDACTED_OPENAI_KEY]", sanitized)
        self.assertIn("[REDACTED_ANTHROPIC_KEY]", sanitized)

    def test_sanitize_bearer_and_passwords(self):
        payload = {
            "auth": "Bearer secret_jwt_token_1234567890_xyz",
            "db_pass": 'password="SuperSecretPassword123"',
            "nested": [
                {"token": "ghp_123456789012345678901234567890123456"}
            ]
        }
        sanitized = SensitiveDataSanitizer.sanitize_data(payload)
        self.assertNotIn("secret_jwt_token_1234567890_xyz", str(sanitized))
        self.assertNotIn("SuperSecretPassword123", str(sanitized))
        self.assertNotIn("ghp_123456789012345678901234567890123456", str(sanitized))
        self.assertIn("[REDACTED_GITHUB_TOKEN]", str(sanitized))


if __name__ == "__main__":
    unittest.main()
