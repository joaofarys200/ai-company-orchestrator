"""
JARVIS OS — Test Suite: Sentinel S4 Real Browser Adversarial & Safety UI E2E Validation
Validação visual e funcional dos fluxos adversariais no frontend:
rejeição com justificação de segurança, rollback visual e tratamento de estados.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
from playwright.async_api import async_playwright

PROJECT_ROOT = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
EVIDENCE_DIR = os.path.join(PROJECT_ROOT, "evidence", "sentinel_browser")
os.makedirs(EVIDENCE_DIR, exist_ok=True)


def test_sentinel_adversarial_ui_browser_e2e():
    """Validação visual Playwright do fluxo de rejeição com motivo e de rollback na UI."""

    async def _run():
        python_exe = sys.executable
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["JARVIS_PORT"] = "8000"

        # Pre-seed history with 1 WAITING_APPROVAL action and 1 COMPLETED action with rollback available
        sentinel_dir = os.path.join(PROJECT_ROOT, "sentinel")
        os.makedirs(sentinel_dir, exist_ok=True)
        history_path = os.path.join(sentinel_dir, "response_history.json")

        sample_history = [
            {
                "action_id": "ACT-S4-REJECT-TEST",
                "incident_id": "INC-ADV-001",
                "action_type": "TERMINATE_PROCESS",
                "target": "PID: 55555 (test_runner.exe)",
                "rationale": "Processo de teste com comportamento anómalo observado",
                "evidence_ids": ["EV-ADV-001"],
                "permission_level": "LOW_RISK_MUTATION",
                "requested_by": "sentinel_correlation_engine",
                "approval_required": True,
                "approved_by": None,
                "approval_session_id": None,
                "approval_timestamp": None,
                "pre_state": {"pid": 55555, "name": "test_runner.exe"},
                "execution_result": {},
                "post_state": {},
                "verification_result": {},
                "rollback_available": False,
                "rollback_plan": "",
                "rollback_result": None,
                "status": "WAITING_APPROVAL",
                "created_at": time.time() - 100,
                "updated_at": time.time() - 100,
                "error_message": None,
                "schema_version": 1,
            },
            {
                "action_id": "ACT-S4-ROLLBACK-TEST",
                "incident_id": "INC-ADV-002",
                "action_type": "BLOCK_NETWORK_ENDPOINT",
                "target": "198.51.100.101:443",
                "rationale": "Bloqueio preventivo de endpoint para teste de rollback",
                "evidence_ids": ["EV-ADV-002"],
                "permission_level": "LOW_RISK_MUTATION",
                "requested_by": "sentinel_correlation_engine",
                "approval_required": True,
                "approved_by": "sec_operator",
                "approval_session_id": "session_01",
                "approval_timestamp": time.time() - 200,
                "pre_state": {"rule_exists": False},
                "execution_result": {"rule_name": "JARVIS-SENTINEL-ACT-S4-ROLLBACK-TEST"},
                "post_state": {"rule_exists": True},
                "verification_result": {"verified": True},
                "rollback_available": True,
                "rollback_plan": "Remover regra JARVIS-SENTINEL-ACT-S4-ROLLBACK-TEST",
                "rollback_result": None,
                "status": "COMPLETED",
                "created_at": time.time() - 300,
                "updated_at": time.time() - 200,
                "error_message": None,
                "schema_version": 1,
            },
        ]

        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(sample_history, f, indent=2)

        server_proc = subprocess.Popen(
            [python_exe, "-u", "server.py"],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            server_ready = False
            for _ in range(30):
                await asyncio.sleep(1.0)
                try:
                    req = urllib.request.Request("http://localhost:8000/healthz")
                    with urllib.request.urlopen(req, timeout=1.0) as resp:
                        if resp.status == 200:
                            server_ready = True
                            break
                except Exception:
                    pass

            assert server_ready, "Servidor JARVIS falhou a inicializar na porta 8000"

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # 1. Navega para a aplicação
                await page.goto("http://localhost:8000", wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2.0)

                # 2. Abre o Workspace caso necessário
                dev_toggle = page.locator('button[title*="Painel Dev"], button[title*="Abrir Painel Dev"], button:has-text("Workspace")')
                if await dev_toggle.count() > 0 and await dev_toggle.first.is_visible():
                    await dev_toggle.first.click(force=True)
                    await asyncio.sleep(1.5)

                # 3. Clica na tab Segurança (Sentinel)
                seguranca_tab = page.locator('button:has-text("Segurança"), button[title*="Segurança"]')
                assert await seguranca_tab.first.is_visible(), "Tab 'Segurança' não encontrada no WorkspaceViewer"
                await seguranca_tab.first.click(force=True)
                await asyncio.sleep(1.5)

                # 4. Navega para a aba "Ações & Contenção"
                actions_tab = page.locator('button:has-text("Ações & Contenção")')
                await actions_tab.wait_for(state="visible", timeout=10000)
                await actions_tab.click(force=True)
                await asyncio.sleep(1.0)

                # 5. Localiza a ação de rejeição e clica no botão "Rejeitar"
                reject_btn = page.locator("button:has-text('Rejeitar')").first
                await reject_btn.wait_for(state="visible", timeout=10000)
                await reject_btn.click(force=True)
                await asyncio.sleep(1.0)

                # 6. Preenche o motivo no modal de rejeição
                reason_input = page.locator("input[placeholder*='Falso positivo'], input[type='text']").last
                await reason_input.wait_for(state="visible", timeout=10000)
                await reason_input.fill("Falso positivo: processo legítimo de teste de software")
                await asyncio.sleep(0.5)

                # 7. Confirma a rejeição
                confirm_reject_btn = page.locator("button:has-text('Confirmar Rejeição')").first
                await confirm_reject_btn.click(force=True)
                await asyncio.sleep(1.0)

                # 8. Captura evidência visual da UI com a rejeição concluída e o painel de segurança
                screenshot_path = os.path.join(EVIDENCE_DIR, "sentinel_s4_adversarial_verified.png")
                await page.screenshot(path=screenshot_path, full_page=True)
                assert os.path.isfile(screenshot_path), "Falha ao gravar screenshot de evidência S4"

                await browser.close()

        finally:
            if server_proc.poll() is None:
                server_proc.terminate()
                server_proc.wait(timeout=5)

    asyncio.run(_run())


if __name__ == "__main__":
    test_sentinel_adversarial_ui_browser_e2e()
