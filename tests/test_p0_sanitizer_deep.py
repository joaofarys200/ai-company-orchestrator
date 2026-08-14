from __future__ import annotations

import unittest
from backend.security.sanitizer import SensitiveDataSanitizer


class TestDeepCredentialSanitization(unittest.TestCase):
    def test_github_tokens_classic_and_fine_grained(self):
        classic_token = "ghp_1234567890abcdef1234567890abcdef12"  # 34 chars
        fine_grained = "github_pat_11ABCD_1234567890abcdefghijklmnopqrstuvwxyz"
        raw = f"Deploying with {classic_token} and fallback {fine_grained}"
        sanitized = SensitiveDataSanitizer.sanitize_text(raw)
        self.assertNotIn(classic_token, sanitized)
        self.assertNotIn(fine_grained, sanitized)
        self.assertIn("[REDACTED_GITHUB_TOKEN]", sanitized)
        self.assertIn("[REDACTED_GITHUB_PAT]", sanitized)

    def test_ai_provider_keys(self):
        openai_key = "sk-proj-1234567890abcdef1234567890abcdef"
        anthropic_key = "sk-ant-api03-abcdef1234567890abcdef1234567890"
        google_key = "AIzaSyA1234567890abcdef1234567890abcdef"
        raw = f"Keys: OpenAI={openai_key}, Anthropic={anthropic_key}, Google={google_key}"
        sanitized = SensitiveDataSanitizer.sanitize_text(raw)
        self.assertNotIn(openai_key, sanitized)
        self.assertNotIn(anthropic_key, sanitized)
        self.assertNotIn(google_key, sanitized)

    def test_bearer_and_jwt_tokens(self):
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgN_w"
        raw = f"Header: Bearer {jwt}"
        sanitized = SensitiveDataSanitizer.sanitize_text(raw)
        self.assertNotIn(jwt, sanitized)

    def test_nested_data_structures(self):
        nested = {
            "user": "admin",
            "password": "super_secret_password_123",
            "metadata": {
                "api_key": "sk-1234567890abcdef1234567890",
                "tokens": ["ghp_1234567890abcdef1234567890abcdef12"],
            },
        }
        sanitized = SensitiveDataSanitizer.sanitize_data(nested)
        self.assertIn("[REDACTED", sanitized["password"])
        self.assertIn("[REDACTED", sanitized["metadata"]["api_key"])
        self.assertIn("[REDACTED_GITHUB_TOKEN]", sanitized["metadata"]["tokens"][0])

    def test_exception_and_env_sanitization(self):
        exc = ValueError("Connection failed with key: sk-ant-1234567890abcdef12345678")
        sanitized = SensitiveDataSanitizer.sanitize_data(exc)
        self.assertNotIn("sk-ant-1234567890abcdef12345678", sanitized)


if __name__ == "__main__":
    unittest.main()
