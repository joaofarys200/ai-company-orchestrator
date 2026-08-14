from __future__ import annotations

import asyncio
import unittest
from backend.gateway.deployment_gateway import WebDeploymentGateway


class TestDeployRealityValidation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gateway = WebDeploymentGateway()

    async def test_empty_page_is_rejected_even_if_status_200(self):
        empty_html = "<html><body></body></html>"
        self.gateway.deploy_local_mvp(empty_html)
        is_ok, msg, details = await self.gateway.verify_deployment_health()
        self.assertFalse(is_ok)
        self.assertIn("vazio", msg.lower())

    async def test_fatal_javascript_pageerror_is_rejected(self):
        broken_html = """
        <html>
            <head><title>Broken App</title></head>
            <body>
                <h1>Broken JS Page</h1>
                <button>Click</button>
                <script>
                    throw new Error("CRITICAL_PAGE_CRASH_UNCAUGHT");
                </script>
            </body>
        </html>
        """
        self.gateway.deploy_local_mvp(broken_html)
        is_ok, msg, details = await self.gateway.verify_deployment_health()
        self.assertFalse(is_ok)
        self.assertTrue(len(details.get("page_errors", [])) > 0 or len(details.get("console_errors", [])) > 0)
        self.assertIn("erro", msg.lower())

    async def test_no_interactive_or_structural_elements_rejected(self):
        flat_html = "<html><body>Just some text without any headings or forms or buttons.</body></html>"
        self.gateway.deploy_local_mvp(flat_html)
        is_ok, msg, details = await self.gateway.verify_deployment_health()
        self.assertFalse(is_ok)
        self.assertIn("elemento", msg.lower())

    async def test_healthy_functional_page_is_approved(self):
        valid_html = """
        <!DOCTYPE html>
        <html>
            <head><title>Micro-SaaS Landing Page</title></head>
            <body>
                <h1>Autonomous Invoice Tracker</h1>
                <p>Welcome to our professional SaaS platform.</p>
                <form action="/submit" method="POST">
                    <input type="email" placeholder="Enter your email" required />
                    <button type="submit">Get Early Access</button>
                </form>
            </body>
        </html>
        """
        self.gateway.deploy_local_mvp(valid_html)
        is_ok, msg, details = await self.gateway.verify_deployment_health()
        self.assertTrue(is_ok)
        self.assertEqual(details["forms_count"], 1)
        self.assertEqual(details["buttons_count"], 1)
        self.assertTrue(details["screenshot_sha256"] is not None)
        self.assertEqual(len(details["page_errors"]), 0)


if __name__ == "__main__":
    unittest.main()
