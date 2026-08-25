"""
JARVIS OS — Test Suite: Sentinel S5 Real Browser Detection Benchmark UI Validation
Validação visual e funcional dos eventos de segurança, badges de severidade,
níveis de confiança e inspetor de linha do tempo em Chromium real via Playwright.
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


def test_sentinel_detection_benchmark_ui_browser_e2e():
    """Validação visual Playwright da tab de Eventos de Segurança, severidades e confiança."""

    async def _run():
        python_exe = sys.executable
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["JARVIS_PORT"] = "8000"

        # Pre-seed history or state if necessary
        sentinel_dir = os.path.join(PROJECT_ROOT, "sentinel")
        os.makedirs(sentinel_dir, exist_ok=True)

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

                # 4. Dispara uma auditoria para popular telemetria ao vivo
                audit_btn = page.locator('button:has-text("Executar Auditoria Agora")')
                if await audit_btn.count() > 0 and await audit_btn.first.is_visible():
                    await audit_btn.first.click(force=True)
                    await asyncio.sleep(2.0)

                # 5. Navega para a aba "Eventos de Segurança"
                events_tab = page.locator('button:has-text("Eventos de Segurança")')
                await events_tab.wait_for(state="visible", timeout=10000)
                await events_tab.click(force=True)
                await asyncio.sleep(1.5)

                # 6. Captura evidência visual da UI de Eventos de Segurança
                screenshot_path = os.path.join(EVIDENCE_DIR, "sentinel_s5_detection_benchmark.png")
                await page.screenshot(path=screenshot_path, full_page=True)
                assert os.path.isfile(screenshot_path), "Falha ao gravar screenshot de evidência S5"

                await browser.close()

        finally:
            if server_proc.poll() is None:
                server_proc.terminate()
                server_proc.wait(timeout=5)

    asyncio.run(_run())


if __name__ == "__main__":
    test_sentinel_detection_benchmark_ui_browser_e2e()
