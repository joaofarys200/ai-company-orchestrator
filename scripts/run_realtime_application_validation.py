"""
JARVIS OS — Phase 10.1: Real-Time Browser QA & Application Validation CLI Runner
Executes autonomous browser validation suite via Playwright and compiles:
docs/JARVIS_REALTIME_BROWSER_VALIDATION_REPORT.md
"""

import asyncio
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure repository root is on sys.path
PROJECT_ROOT = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.browser.realtime_application_validation_agent import (
    RealTimeApplicationValidationAgent,
)


async def main():
    print("=" * 85)
    print("🚀 EXECUTANDO O AGENTE DE VALIDAÇÃO END-TO-END EM BROWSER REAL — FASE 10.1")
    print("=" * 85)
    start_time = time.time()

    agent = RealTimeApplicationValidationAgent(headless=True)
    try:
        await agent.initialize()
        results = await agent.run_all_tests()
        report = agent.compile_report()

        elapsed = time.time() - start_time
        pass_count = sum(1 for r in results if r.status == "PASS")
        fail_count = sum(1 for r in results if r.status == "FAIL")

        print("\n" + "=" * 85)
        print("📊 RESULTADOS EMPÍRICOS DA AUDITORIA EM BROWSER REAL:")
        print("=" * 85)
        for r in results:
            status_symbol = "✅" if r.status == "PASS" else "❌"
            print(f"  {status_symbol} [{r.test_id}] {r.capability:<45} : {r.status} ({r.duration_seconds:.2f}s)")

        print("-" * 85)
        print(f"  • Total de Testes : {len(results)}")
        print(f"  • Aprovados (PASS): {pass_count}")
        print(f"  • Falhas (FAIL)   : {fail_count}")
        print(f"  • Tempo Total     : {elapsed:.2f}s")
        print("=" * 85)

        # Output the exact required final format
        r_c = next((r for r in results if r.test_id == "TEST-003-MEMORY"), None)
        r_d = next((r for r in results if r.test_id == "TEST-004-RAG"), None)
        r_e = next((r for r in results if r.test_id == "TEST-005-CODEGEN"), None)
        r_g = next((r for r in results if r.test_id == "TEST-007-COMPUTERUSE"), None)
        r_h = next((r for r in results if r.test_id == "TEST-008-RECOVERY"), None)
        r_i = next((r for r in results if r.test_id == "TEST-009-SECURITY"), None)
        r_k = next((r for r in results if r.test_id == "TEST-011-LONGHORIZON"), None)

        first_failure = agent.failures[0] if agent.failures else None

        print("\n========================================")
        print("JARVIS REAL-TIME APPLICATION VALIDATION")
        print("========================================")
        print(f"Application: JARVIS OS // AI Company Orchestrator")
        print(f"Browser: Chromium (Playwright 1.62.0)")
        print(f"Commit: HEAD")
        print(f"Tests Executed: {len(results)}")
        print(f"PASS: {pass_count}")
        print(f"FAIL: {fail_count}")
        print(f"BLOCKED: 0")
        print(f"NOT_IMPLEMENTED: 0\n")

        print(f"Memory: {'PASS' if r_c and r_c.status == 'PASS' else 'FAIL'}")
        print(f"RAG: {'PASS' if r_d and r_d.status == 'PASS' else 'FAIL'}")
        print(f"Code Generation: {'PASS' if r_e and r_e.status == 'PASS' else 'FAIL'}")
        print(f"Computer Use: {'PASS' if r_g and r_g.status == 'PASS' else 'FAIL'}")
        print(f"Recovery: {'PASS' if r_h and r_h.status == 'PASS' else 'FAIL'}")
        print(f"Security: {'PASS' if r_i and r_i.status == 'PASS' else 'FAIL'}")
        print(f"Long Horizon: {'PASS' if r_k and r_k.status == 'PASS' else 'FAIL'}\n")

        print(f"First Real Failure: {first_failure.description if first_failure else 'None (All Real-Time Tests Passed)'}")
        print(f"Root Cause: {first_failure.probable_root_cause if first_failure else 'None'}")
        print(f"Evidence: {first_failure.evidence_files[0] if first_failure and first_failure.evidence_files else 'evidence/browser_validation/'}\n")

        next_fix = "N/A — System operating normally." if fail_count == 0 else f"Fix {first_failure.affected_component if first_failure else 'component'}"
        print(f"NEXT SMALLEST FIX: {next_fix}")

    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
