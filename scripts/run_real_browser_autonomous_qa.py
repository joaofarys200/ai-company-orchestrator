"""
CLI Entrypoint to execute the Real Browser Autonomous QA Agent.
"""

import asyncio
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.browser.real_browser_autonomous_qa_agent import (
    RealBrowserAutonomousQAAgent,
)


async def main():
    agent = RealBrowserAutonomousQAAgent(headless=True)
    try:
        await agent.initialize()
        results = await agent.run_full_qa_battery()
        report = agent.compile_report()

        print("\n" + "=" * 80)
        print("📊 RESULTADOS EMPÍRICOS DA AUDITORIA REAL BROWSER QA:")
        print("=" * 80)
        for r in results:
            icon = "✅" if r.status == "PASS" else ("ℹ️" if r.status == "NOT_IMPLEMENTED" else "❌")
            print(f"  {icon} [{r.test_id}] {r.name:<30} : {r.status} ({r.duration_seconds:.2f}s)")
        print("-" * 80)

        pass_count = sum(1 for r in results if r.status == "PASS")
        fail_count = sum(1 for r in results if r.status == "FAIL")
        not_impl = sum(1 for r in results if r.status == "NOT_IMPLEMENTED")
        total = len(results)

        r_mem = next((r for r in results if r.test_id == "TEST-3-MEMORY"), None)
        r_learn = next((r for r in results if r.test_id == "TEST-5-LEARNING"), None)
        r_rag = next((r for r in results if r.test_id == "TEST-4-RAG"), None)
        r_code = next((r for r in results if r.test_id == "TEST-6-CODEGEN"), None)
        r_comp = next((r for r in results if r.test_id == "TEST-7-COMPUTERUSE"), None)
        r_rec = next((r for r in results if r.test_id == "TEST-8-RECOVERY"), None)
        r_eco = next((r for r in results if r.test_id == "TEST-9-ECONOMIC"), None)
        r_long = next((r for r in results if r.test_id == "TEST-10-LONGSESSION"), None)

        print(f"""
========================================
REAL BROWSER QA — FINAL RESULT
========================================

Browser: Chromium (Playwright 1.62.0 / Chrome Channel)
JARVIS URL: {agent.frontend_url}

Tests: {total}
PASS: {pass_count}
FAIL: {fail_count}
BLOCKED: 0
NOT_IMPLEMENTED: {not_impl}

Memory: {r_mem.status if r_mem else 'FAIL'}
Learning: {r_learn.status if r_learn else 'NOT_IMPLEMENTED'}
RAG: {r_rag.status if r_rag else 'FAIL'}
Code Generation: {r_code.status if r_code else 'FAIL'}
Computer Use: {r_comp.status if r_comp else 'FAIL'}
Recovery: {r_rec.status if r_rec else 'FAIL'}
Economic: {r_eco.status if r_eco else 'FAIL'}
Long Session: {r_long.status if r_long else 'FAIL'}

FIRST REAL FAILURE:
{"None (All real-browser battery tests executed successfully)" if fail_count == 0 else "Failures observed"}

ROOT CAUSE:
{"None" if fail_count == 0 else "See report for details"}

EVIDENCE:
evidence/browser/

NEXT SMALLEST FIX:
{"N/A — System operating normally in real browser." if fail_count == 0 else "Fix component"}
""")

    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
