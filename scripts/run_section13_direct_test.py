import sys
import time
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(r"C:\Users\joaor\.gemini\antigravity-ide\brain\53b9c83c-04cb-413d-9610-65cb1ea8e073")

def test_direct():
    print("=" * 60)
    print("RUNNING SECTION 13 CONTROLLED TEST: direct_pdf_test.html")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 1000})

        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        print("Navigating to http://localhost:8000/direct_pdf_test.html ...")
        page.goto("http://localhost:8000/direct_pdf_test.html", wait_until="networkidle", timeout=15000)

        # Wait for diagnostic verdict
        for _ in range(30):
            diag = page.evaluate("() => window.__DIAGNOSTIC__")
            if diag and diag.get("verdict") != "PENDING":
                break
            time.sleep(0.5)

        diag = page.evaluate("() => window.__DIAGNOSTIC__")
        print("\nDIAGNOSTIC RESULTS:")
        print(json.dumps(diag, indent=2))

        screenshot_path = ARTIFACTS_DIR / "section13_direct_pdf_render.png"
        page.screenshot(path=str(screenshot_path))
        print(f"\nCaptured screenshot: {screenshot_path}")

        print("\nCONSOLE LOGS:")
        for log in console_logs:
            print(log)

        browser.close()

        if diag and diag.get("verdict") == "PASS":
            print("\nRESULT: PDF_RENDER_DIRECT = PASS")
            return True
        else:
            print(f"\nRESULT: PDF_RENDER_DIRECT = FAIL ({diag.get('render_error')})")
            return False

if __name__ == "__main__":
    success = test_direct()
    sys.exit(0 if success else 1)
