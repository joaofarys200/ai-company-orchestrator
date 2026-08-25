"""
JARVIS OS — Test Suite: Sentinel S3 Human-Approved Response & Containment Browser E2E Validation
Validação visual e funcional do painel de Ações & Contenção e modal de aprovação humana.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
import pytest
from playwright.async_api import async_playwright

PROJECT_ROOT = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
EVIDENCE_DIR = os.path.join(PROJECT_ROOT, "evidence", "sentinel_browser")
os.makedirs(EVIDENCE_DIR, exist_ok=True)


def test_sentinel_response_actions_browser_e2e():
    """Validação visual da aba Ações & Contenção, banner de segurança humana e modal de aprovação."""

    async def _run():
        python_exe = sys.executable
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["JARVIS_PORT"] = "8000"

        # Pre-seed a proposed response action in response_history.json for visual verification
        sentinel_dir = os.path.join(PROJECT_ROOT, "sentinel")
        os.makedirs(sentinel_dir, exist_ok=True)
        history_path = os.path.join(sentinel_dir, "response_history.json")

        sample_history = {
            "ACT-PROC-E2E-TEST": {
                "action_id": "ACT-PROC-E2E-TEST",
                "incident_id": "INC-E2E-001",
                "action_type": "TERMINATE_PROCESS",
                "target": "PID: 49152 (evil_cryptominer.exe)",
                "rationale": "Processo suspeito não-assinado em execução a partir de AppData\\Local\\Temp com alto consumo de CPU",
                "evidence_ids": ["EV-PROC-TEMP-001", "EV-NET-SUSP-002"],
                "permission_level": "LOW_RISK_MUTATION",
                "requested_by": "sentinel_correlation_engine",
                "approval_required": True,
                "approved_by": None,
                "approval_session_id": None,
                "approval_timestamp": None,
                "pre_state": {"pid": 49152, "name": "evil_cryptominer.exe", "path": "C:\\Temp\\evil_cryptominer.exe"},
                "execution_result": {},
                "post_state": {},
                "verification_result": {},
                "rollback_available": False,
                "rollback_plan": "Reversão não aplicável a finalização de processos",
                "rollback_result": None,
                "status": "WAITING_APPROVAL",
                "created_at": time.time() - 120,
                "updated_at": time.time() - 120,
                "error_message": None,
                "schema_version": 1,
            },
            "ACT-NET-E2E-TEST": {
                "action_id": "ACT-NET-E2E-TEST",
                "incident_id": "INC-E2E-002",
                "action_type": "BLOCK_NETWORK_ENDPOINT",
                "target": "198.51.100.42:443",
                "rationale": "Tentativa reiterada de beaconing C2 para endereço IP não catalogado",
                "evidence_ids": ["EV-NET-C2-001"],
                "permission_level": "LOW_RISK_MUTATION",
                "requested_by": "sentinel_correlation_engine",
                "approval_required": True,
                "approved_by": "human_operator",
                "approval_session_id": "session_admin_01",
                "approval_timestamp": time.time() - 300,
                "pre_state": {"rule_exists": False},
                "execution_result": {"rule_name": "JARVIS-SENTINEL-ACT-NET-E2E-TEST", "action": "BLOCK"},
                "post_state": {"rule_exists": True},
                "verification_result": {"verified": True, "reason": "Regra ativa no Windows Firewall"},
                "rollback_available": True,
                "rollback_plan": "Remover regra JARVIS-SENTINEL-ACT-NET-E2E-TEST",
                "rollback_result": None,
                "status": "COMPLETED",
                "created_at": time.time() - 600,
                "updated_at": time.time() - 300,
                "error_message": None,
                "schema_version": 1,
            },
        }

        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(list(sample_history.values()), f, indent=2)

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

                # 1. Carrega a aplicação
                await page.goto("http://localhost:8000", wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2.0)

                # 2. Abre o Workspace caso não esteja aberto
                dev_toggle = page.locator('button[title*="Painel Dev"], button[title*="Abrir Painel Dev"], button:has-text("Workspace")')
                if await dev_toggle.count() > 0 and await dev_toggle.first.is_visible():
                    await dev_toggle.first.click(force=True)
                    await asyncio.sleep(1.5)

                # 3. Clica na tab Segurança (Sentinel)
                seguranca_tab = page.locator('button:has-text("Segurança"), button[title*="Segurança"]')
                assert await seguranca_tab.first.is_visible(), "Tab 'Segurança' não encontrada no WorkspaceViewer"
                await seguranca_tab.first.click(force=True)
                await asyncio.sleep(1.5)

                # 4. Clica na sub-aba "Ações & Contenção"
                actions_tab = page.locator('button:has-text("Ações & Contenção")')
                await actions_tab.wait_for(state="visible", timeout=10000)
                assert await actions_tab.is_visible()
                await actions_tab.click(force=True)
                await asyncio.sleep(1.0)

                # 5. Verifica a presença do banner de aviso de resposta defensiva
                policy_banner = page.locator("text=Política de Resposta & Contenção Defensiva")
                await policy_banner.wait_for(state="visible", timeout=5000)
                assert await policy_banner.is_visible()

                # 6. Verifica presença das ações de teste
                proc_action = page.locator("text=ACT-PROC-E2E-TEST").first
                await proc_action.wait_for(state="visible", timeout=5000)
                assert await proc_action.is_visible()

                net_action = page.locator("text=ACT-NET-E2E-TEST").first
                assert await net_action.is_visible()

                # 7. Clica no botão "Aprovar e Executar" para abrir o modal de confirmação de segurança
                approve_btn = page.locator("button:has-text('Aprovar e Executar')").first
                await approve_btn.click(force=True)
                await asyncio.sleep(0.8)

                # 8. Verifica modal de aprovação humana e aviso explícito
                modal_title = page.locator("text=Autorização de Resposta Defensiva").first
                await modal_title.wait_for(state="visible", timeout=5000)
                assert await modal_title.is_visible()

                modal_warning = page.locator("text=ESTA AÇÃO ALTERARÁ O SISTEMA").first
                assert await modal_warning.is_visible()

                # 9. Captura evidência visual do modal e do painel S3
                screenshot_path = os.path.join(EVIDENCE_DIR, "sentinel_s3_response_verified.png")
                await page.screenshot(path=screenshot_path, full_page=True)
                assert os.path.isfile(screenshot_path), "Falha ao gravar screenshot de evidência S3"

                await browser.close()

        finally:
            if server_proc.poll() is None:
                server_proc.terminate()
                server_proc.wait(timeout=5)

    asyncio.run(_run())


if __name__ == "__main__":
    test_sentinel_response_actions_browser_e2e()
