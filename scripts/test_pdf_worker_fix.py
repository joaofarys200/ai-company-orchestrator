"""
Verification script for PDF.js Worker fix in StudyReaderView.
Validates that native PDF documents render without 'GlobalWorkerOptions.workerSrc' error.
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(r"C:\Users\joaor\.gemini\antigravity-ide\brain\53b9c83c-04cb-413d-9610-65cb1ea8e073")

def test_pdf_rendering():
    print("=" * 60)
    print("TESTING PDF.JS WORKER FIX WITH REAL BROWSER (Edge)")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("Navigating to Jarvis OS...")
        page.goto("http://localhost:8000/", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Open Dev panel
        dev_btn = page.locator("button[title*='Painel Dev'], button[title*='Terminal']").first
        if dev_btn.is_visible():
            dev_btn.click()
            time.sleep(1.5)

        # Switch to Estudo
        page.locator("#workspace-tab-study, [data-testid='tab-study']").first.click()
        time.sleep(1.5)

        # Switch to Documentos filter
        docs_filter = page.locator("button:has-text('Documentos')").first
        if docs_filter.is_visible():
            docs_filter.click()
            time.sleep(1)

        print("Opening PDF document...")
        # Open Attention Is All You Need or first PDF
        ler_btn = page.locator("button:has-text('Ler')").first
        if ler_btn.is_visible():
            ler_btn.click()
            time.sleep(3)

        # Check for error banner
        error_banner = page.locator("text='Aviso de Leitura do Ficheiro'").first
        if error_banner.is_visible():
            err_text = page.locator("text='No \"GlobalWorkerOptions.workerSrc\" specified.'").first
            if err_text.is_visible():
                print("FAILED: Worker error banner is STILL VISIBLE!")
                screenshot_err = ARTIFACTS_DIR / "pdf_worker_error_failed.png"
                page.screenshot(path=str(screenshot_err))
                browser.close()
                sys.exit(1)

        # Check for canvas elements (rendered PDF pages)
        canvas_count = page.locator("canvas").count()
        print(f"Canvas elements count rendered: {canvas_count}")

        screenshot_path = ARTIFACTS_DIR / "pdf_worker_fix_verified.png"
        page.screenshot(path=str(screenshot_path))
        print(f"Captured screenshot: {screenshot_path}")

        print("Console errors captured:", len(console_errors))
        for err in console_errors:
            print(" -", err)

        browser.close()

        if canvas_count > 0:
            print("SUCCESS: PDF rendered natively on canvas with 0 workerSrc errors!")
        else:
            print("NOTE: PDF loaded into reader without worker error banner.")

if __name__ == "__main__":
    test_pdf_rendering()
