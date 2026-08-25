"""
JARVIS OS — Phase 10.1: Real-Time Browser QA & Application Validation Test Suite
"""

import asyncio
import os
import sys
import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.browser.realtime_application_validation_agent import (
    RealTimeApplicationValidationAgent,
)


def test_realtime_browser_application_validation():
    """
    Executes the full end-to-end autonomous browser validation agent suite
    against the real JARVIS application via Playwright.
    """
    async def _run():
        agent = RealTimeApplicationValidationAgent(headless=True)
        try:
            await agent.initialize()
            results = await agent.run_all_tests()
            agent.compile_report()

            assert len(results) >= 10, f"Expected >= 10 tests, got {len(results)}"

            boot_test = next((r for r in results if r.test_id == "TEST-001-BOOT"), None)
            assert boot_test is not None, "TEST-001-BOOT result not found"
            assert boot_test.status == "PASS", f"Boot reality gate failed: {boot_test.details}"

            fail_count = sum(1 for r in results if r.status == "FAIL")
            assert fail_count == 0, f"Observed {fail_count} test failures"

        finally:
            await agent.close()

    asyncio.run(_run())
