"""
JARVIS OS — Test Suite: Sentinel S2.5 Startup & Lifecycle Browser E2E Validation
Validação visual em browser real Playwright com verificação de não-regressão.
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


def test_sentinel_startup_lifecycle_browser_e2e():
    """Validação visual do ciclo de vida de arranque do Sentinel e não-regressão do Workspace."""

    async def _run():
        python_exe = sys.executable
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["JARVIS_PORT"] = "8000"

        # Inicia o servidor Python com saída descartada
        server_proc = subprocess.Popen(
            [python_exe, "-u", "server.py"],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            # Aguarda o servidor HTTP/WebSocket ficar disponível
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

                # 4. Verifica título do Sentinel
                header = page.locator("text=JARVIS SECURITY SENTINEL")
                await header.wait_for(state="visible", timeout=10000)
                assert await header.is_visible()

                # 5. Navega pelas abas do dashboard
                for tab_name in ["Processos", "Rede & Portas", "Persistência", "Extensões", "Eventos de Segurança"]:
                    tab_btn = page.locator(f"button:has-text('{tab_name}')")
                    if await tab_btn.count() > 0:
                        await tab_btn.first.click(force=True)
                        await asyncio.sleep(0.3)

                # Volta para a aba Overview
                overview_btn = page.locator("button:has-text('Overview')")
                if await overview_btn.count() > 0:
                    await overview_btn.first.click(force=True)
                    await asyncio.sleep(0.5)

                # 6. Captura evidência visual de sucesso
                screenshot_path = os.path.join(EVIDENCE_DIR, "sentinel_s2_5_startup_verified.png")
                await page.screenshot(path=screenshot_path, full_page=True)
                assert os.path.isfile(screenshot_path), "Falha ao gravar screenshot de evidência"

                await browser.close()

        finally:
            if server_proc.poll() is None:
                server_proc.terminate()
                try:
                    server_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    server_proc.kill()

    asyncio.run(_run())
