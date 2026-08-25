"""
Pytest integration for Real Browser Autonomous QA Agent.
"""

import asyncio
import os
import sys
import pytest

PROJECT_ROOT = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.browser.real_browser_autonomous_qa_agent import (
    RealBrowserAutonomousQAAgent,
)


def test_real_browser_autonomous_qa_battery():
    """
    Executes the full 10-test real browser QA battery via Playwright.
    """
    async def _run():
        agent = RealBrowserAutonomousQAAgent(headless=True)
        try:
            await agent.initialize()
            results = await agent.run_full_qa_battery()
            report = agent.compile_report()

            assert len(results) >= 10, f"Expected >= 10 tests, got {len(results)}"
            smoke = next((r for r in results if r.test_id == "TEST-1-SMOKE"), None)
            assert smoke is not None and smoke.status == "PASS"

            fail_count = sum(1 for r in results if r.status == "FAIL")
            assert fail_count == 0, f"Encountered {fail_count} failures in real browser QA"

        finally:
            await agent.close()

    asyncio.run(_run())
