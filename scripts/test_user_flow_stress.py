import sys
import time
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(r"C:\Users\joaor\.gemini\antigravity-ide\brain\53b9c83c-04cb-413d-9610-65cb1ea8e073")

def test_stress():
    print("=" * 60)
    print("USER FLOW STRESS TEST: SWITCHING, RELOAD, TABS, PAGES")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ["error", "warning"] else None)

        print("1. Opening app at http://localhost:8000/ ...")
        page.goto("http://localhost:8000/", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Open Dev panel if collapsed
        dev_btn = page.locator("button[title*='Painel Dev'], button[title*='Terminal']").first
        if dev_btn.is_visible():
            dev_btn.click()
            time.sleep(1)

        # Switch to Estudo
        print("2. Switching to Estudo tab...")
        page.locator("#workspace-tab-study, [data-testid='tab-study']").first.click()
        time.sleep(1.5)

        # Switch to Documentos filter
        docs_filter = page.locator("button:has-text('Documentos')").first
        if docs_filter.is_visible():
            docs_filter.click()
            time.sleep(1)

        # Click the "Ler" button for Predicting performance
        print("3. Clicking 'Ler' on Predicting performance...")
        # Find card and button
        ler_btn = page.locator("h2:has-text('Predicting performance online consumer reviews')").first
        ler_btn.click()
        time.sleep(4)

        # Check if spinner is visible
        spinner = page.locator("text='A carregar o artigo científico em alta resolução...'").first
        print(f"Initial check - Spinner visible: {spinner.is_visible()}")

        # Check canvas
        canvas1 = page.locator("div[id^='pdf-page-1'] canvas").first
        print(f"Initial check - Page 1 canvas visible: {canvas1.is_visible()}")

        # Step 4: Click "Recarregar documento" button if visible, or test reloadKey
        print("4. Testing 'Recarregar documento' / reload trigger...")
        reload_btn = page.locator("button[title='Tentar recarregar ficheiro']").first
        if reload_btn.is_visible():
            print("Clicking 'Recarregar documento'...")
            reload_btn.click()
            time.sleep(4)
            print(f"After reload click - Spinner visible: {spinner.is_visible()}")
            print(f"After reload click - Canvas visible: {canvas1.is_visible()}")

        # Step 5: Switch tabs in study container: "Resumo" -> "Leitura"
        print("5. Switching tabs to 'Resumo' and back to 'Leitura'...")
        resumo_tab = page.locator("button:has-text('Resumo')").first
        if resumo_tab.is_visible():
            resumo_tab.click()
            time.sleep(1.5)
            leitura_tab = page.locator("button:has-text('Leitura')").first
            leitura_tab.click()
            time.sleep(3)
            print(f"After tab switch - Spinner visible: {spinner.is_visible()}")
            print(f"After tab switch - Canvas visible: {canvas1.is_visible()}")

        # Step 6: Go back to Library and open again
        print("6. Going back to Library and reopening...")
        back_btn = page.locator("button[title='Voltar à Biblioteca']").first
        if back_btn.is_visible():
            back_btn.click()
            time.sleep(1.5)
            # Reopen
            page.locator("h2:has-text('Predicting performance online consumer reviews')").first.click()
            time.sleep(4)
            print(f"After library reopen - Spinner visible: {spinner.is_visible()}")
            print(f"After library reopen - Canvas visible: {canvas1.is_visible()}")

        # Step 7: Take final screenshot
        screenshot_path = ARTIFACTS_DIR / "stress_test_result.png"
        page.screenshot(path=str(screenshot_path))
        print(f"\nCaptured screenshot: {screenshot_path}")

        print("\nConsole warnings/errors:")
        for err in console_errors:
            print(err)

        browser.close()

if __name__ == "__main__":
    test_stress()
