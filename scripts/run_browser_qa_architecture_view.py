"""
Browser QA script to validate and capture screenshots of:
1. Code Editor with file explorer AST badges and entrypoint indicators.
2. Architecture & AST blueprint dashboard with symbols, entrypoints, dependencies, and cognition cards.
"""

import asyncio
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from playwright.async_api import async_playwright

PROJECT_ROOT = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
DOCS_SCREENSHOTS = os.path.join(PROJECT_ROOT, "docs", "screenshots")
ARTIFACT_DIR = r"C:\Users\joaor\.gemini\antigravity-ide\brain\abaf1302-2103-48c3-a081-a23167066412"
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

os.makedirs(DOCS_SCREENSHOTS, exist_ok=True)
os.makedirs(ARTIFACT_DIR, exist_ok=True)


async def main():
    print("=" * 80)
    print(" BROWSER QA — ARCHITECTURE & AST VISUAL INSPECTOR")
    print("=" * 80)

    python_exe = sys.executable
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["JARVIS_PORT"] = "8000"

    print(" -> Starting backend server on port 8000...")
    server_proc = subprocess.Popen(
        [python_exe, "-u", "server.py"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Wait for healthz
        server_ready = False
        for i in range(35):
            await asyncio.sleep(1.0)
            try:
                req = urllib.request.Request("http://127.0.0.1:8000/healthz")
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status == 200:
                        server_ready = True
                        print(f" -> Server ready after {i+1}s.")
                        break
            except Exception:
                pass

        if not server_ready:
            print("ERROR: Server failed to start.")
            return

        async with async_playwright() as p:
            print(f" -> Launching Chromium Edge: {EDGE_PATH}")
            browser = await p.chromium.launch(
                executable_path=EDGE_PATH,
                headless=True,
                args=["--no-sandbox", "--disable-gpu", "--hide-scrollbars"],
            )
            context = await browser.new_context(viewport={"width": 1600, "height": 950})
            page = await context.new_page()

            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

            print(" -> Navigating to http://127.0.0.1:8000...")
            await page.goto("http://127.0.0.1:8000", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2.0)

            # Open Dev Panel / Workspace
            print(" -> Opening Dev Panel / Workspace...")
            dev_toggle = page.locator('button[title*="Painel Dev"]')
            if await dev_toggle.count() > 0:
                await dev_toggle.first.click(force=True)
                await asyncio.sleep(2.0)

            # Check if Workspace is open, look for "Código" primary tab
            # Click "Ficheiros" tab to ensure Monaco Code Editor is shown
            files_tab = page.locator("button:has-text('Ficheiros'), .workspace-secondary-tab:has-text('Ficheiros')").first
            if await files_tab.count() > 0:
                print(" -> Ensuring 'Ficheiros' tab is active...")
                await files_tab.click(force=True)
                await asyncio.sleep(2.0)

            # Capture Code Editor with AST badges and Entrypoint indicator
            screenshot_code_editor = os.path.join(DOCS_SCREENSHOTS, "code_editor_view.png")
            artifact_code_editor = os.path.join(ARTIFACT_DIR, "code_editor_view.png")
            await page.screenshot(path=screenshot_code_editor, full_page=False)
            shutil.copy2(screenshot_code_editor, artifact_code_editor)
            print(f" -> Captured Code Editor view: {screenshot_code_editor}")

            # Now click on "Arquitetura & AST" tab
            arch_tab = page.locator("button:has-text('Arquitetura & AST'), .workspace-secondary-tab:has-text('Arquitetura & AST')").first
            if await arch_tab.count() > 0:
                print(" -> Clicking 'Arquitetura & AST' secondary tab...")
                await arch_tab.click(force=True)
                await asyncio.sleep(2.5)

            # Capture Architecture & AST View
            screenshot_arch_view = os.path.join(DOCS_SCREENSHOTS, "architecture_ast_view.png")
            artifact_arch_view = os.path.join(ARTIFACT_DIR, "architecture_ast_view.png")
            await page.screenshot(path=screenshot_arch_view, full_page=False)
            shutil.copy2(screenshot_arch_view, artifact_arch_view)
            print(f" -> Captured Architecture & AST view: {screenshot_arch_view}")

            print(f" -> Total console errors: {len(console_errors)}")
            if console_errors:
                for err in console_errors[:5]:
                    print(f"    [CONSOLE ERROR] {err}")

            await browser.close()
            print(" -> Browser closed successfully.")

    finally:
        print(" -> Terminating backend server...")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except Exception:
            server_proc.kill()
        print(" -> Server terminated.")


if __name__ == "__main__":
    asyncio.run(main())
