"""
Real-time browser test for Sentinel Security Dashboard (Fase S2).
"""

import asyncio
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


def test_sentinel_visual_dashboard_e2e():
    """Validação end-to-end em browser real da interface Sentinel Dashboard."""

    async def _run():
        python_exe = sys.executable
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["JARVIS_PORT"] = "8000"

        # Inicia o backend com stdout/stderr DEVNULL para evitar pipe stalls
        server_proc = subprocess.Popen(
            [python_exe, "-u", "server.py"],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            # Aguarda o servidor HTTP/WebSocket inicializar
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

                # 4. Valida presença dos componentes do Sentinel
                banner = page.locator('text=JARVIS SECURITY SENTINEL')
                assert await banner.is_visible(), "Banner do Sentinel não visível"

                fase_badge = page.locator('text=FASE S2: CONTINUOUS WATCHDOG')
                assert await fase_badge.is_visible(), "Badge FASE S2 não visível"

                # 5. Valida KPI cards
                watchdog_kpi = page.locator('text=Watchdog Status')
                assert await watchdog_kpi.is_visible(), "KPI Watchdog Status não visível"

                defender_kpi = page.locator('text=Windows Defender')
                assert await defender_kpi.is_visible(), "KPI Windows Defender não visível"

                # 6. Clica nas sub-tabs
                process_tab = page.locator('button:has-text("Processos")')
                await process_tab.click()
                await asyncio.sleep(0.5)

                network_tab = page.locator('button:has-text("Rede & Portas")')
                await network_tab.click()
                await asyncio.sleep(0.5)

                # 7. Captura screenshot de evidência
                screenshot_path = os.path.join(EVIDENCE_DIR, "sentinel_dashboard_verified.png")
                await page.screenshot(path=screenshot_path, full_page=True)
                assert os.path.exists(screenshot_path), "Screenshot de evidência não gerado"

                # 8. Testa botão de auditoria manual
                audit_btn = page.locator('button:has-text("Executar Auditoria Agora")')
                assert await audit_btn.is_visible(), "Botão Executar Auditoria Agora não visível"
                await audit_btn.click()
                await asyncio.sleep(2.0)

                await browser.close()

        finally:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5.0)
            except Exception:
                server_proc.kill()

    asyncio.run(_run())


if __name__ == "__main__":
    pytest.main(["-v", __file__])
