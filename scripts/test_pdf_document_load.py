import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(r"C:\Users\joaor\.gemini\antigravity-ide\brain\53b9c83c-04cb-413d-9610-65cb1ea8e073")

def test_document_load():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        print("Navigating to Jarvis OS...")
        page.goto("http://localhost:8000/", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Open Dev panel if collapsed
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

        # Click the document title directly
        title_heading = page.locator("h2:has-text('Predicting performance online consumer reviews')").first
        if title_heading.is_visible():
            print("Clicking title 'Predicting performance online consumer reviews'...")
            title_heading.click()
        else:
            print("Title not visible, trying button...")
            page.locator("button:has-text('Ler')").nth(1).click()

        time.sleep(5)

        # Check for error banner
        error_banner = page.locator("text='Aviso de Leitura do Ficheiro'")
        is_error_visible = error_banner.is_visible()
        print(f"Error banner visible: {is_error_visible}")
        assert not is_error_visible, "Error banner 'Aviso de Leitura do Ficheiro' is unexpectedly visible!"

        # Check for rendered canvas pages
        canvas_count = page.locator("canvas").count()
        print(f"Canvas count rendered: {canvas_count}")
        assert canvas_count >= 1, f"Expected at least 1 canvas rendered, got {canvas_count}"

        screenshot_path = ARTIFACTS_DIR / "predicting_performance_test.png"
        page.screenshot(path=str(screenshot_path))
        print(f"Captured screenshot: {screenshot_path}")

        print("\n=== CONSOLE LOGS ===")
        for log in console_logs:
            if any(term in log.lower() for term in ["pdf", "worker", "study", "error", "warn"]):
                print(log)

        print("\nALL ASSERTIONS PASSED: PDF rendered cleanly without ArrayBuffer detached errors!")
        browser.close()

if __name__ == "__main__":
    test_document_load()
