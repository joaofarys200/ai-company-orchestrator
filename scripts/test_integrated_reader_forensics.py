import sys
import time
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(r"C:\Users\joaor\.gemini\antigravity-ide\brain\53b9c83c-04cb-413d-9610-65cb1ea8e073")

def test_integrated():
    print("=" * 60)
    print("SECTION 14: INTEGRATED RENDER FORENSICS")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        console_logs = []
        network_logs = []

        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("request", lambda req: network_logs.append(f"REQ: {req.method} {req.url}"))
        page.on("response", lambda res: network_logs.append(f"RES: {res.status} {res.url} ({res.headers.get('content-type', '')})"))

        print("1. Navigating to Jarvis OS http://localhost:8000/ ...")
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

        # Click the title directly to open reader
        print("3. Opening 'Predicting performance online consumer reviews' in StudyReaderView...")
        title_heading = page.locator("h2:has-text('Predicting performance online consumer reviews')").first
        assert title_heading.is_visible(), "Document title heading not found in library!"
        title_heading.click()

        # Wait 4 seconds for reader state
        time.sleep(4)

        # Inspect DOM states
        loading_spinner = page.locator("text='A carregar o artigo científico em alta resolução...'").first
        is_loading_spinner_visible = loading_spinner.is_visible()
        print(f"\n[DOM CHECK] Loading spinner visible: {is_loading_spinner_visible}")

        error_banner = page.locator("text='Aviso de Leitura do Ficheiro'").first
        is_error_banner_visible = error_banner.is_visible()
        print(f"[DOM CHECK] Error banner visible: {is_error_banner_visible}")

        # Check PDF page containers
        pdf_pages = page.locator("div[id^='pdf-page-']")
        pdf_page_count = pdf_pages.count()
        print(f"[DOM CHECK] PDF page containers (div[id^='pdf-page-']): {pdf_page_count}")

        # Check all canvas elements in detail
        canvases_info = page.evaluate("""() => {
            const all = Array.from(document.querySelectorAll('canvas'));
            return all.map(c => ({
                id: c.id,
                className: c.className,
                width: c.width,
                height: c.height,
                styleWidth: c.style.width,
                styleHeight: c.style.height,
                parentId: c.parentElement ? c.parentElement.id : null,
                parentClass: c.parentElement ? c.parentElement.className : null,
                boundingRect: c.getBoundingClientRect()
            }));
        }""")
        print(f"[DOM CHECK] Total canvas elements: {len(canvases_info)}")
        print(json.dumps(canvases_info, indent=2))

        # Check if page 1 canvas has pixels rendered
        if pdf_page_count > 0:
            pixel_check = page.evaluate("""() => {
                const canvas = document.querySelector("div[id^='pdf-page-'] canvas");
                if (!canvas) return { error: 'No PDF canvas found' };
                const ctx = canvas.getContext('2d');
                if (!ctx) return { error: 'No 2d context' };
                const imgData = ctx.getImageData(0, 0, Math.min(canvas.width, 200), Math.min(canvas.height, 200));
                let nonZero = 0;
                for (let i = 0; i < imgData.data.length; i += 4) {
                    if (imgData.data[i] !== 255 || imgData.data[i+1] !== 255 || imgData.data[i+2] !== 255) {
                        nonZero++;
                    }
                }
                return { width: canvas.width, height: canvas.height, nonZeroPixels: nonZero };
            }""")
            print(f"[PIXEL CHECK] Page 1 canvas pixels:", pixel_check)

        screenshot_path = ARTIFACTS_DIR / "integrated_reader_forensics.png"
        page.screenshot(path=str(screenshot_path))
        print(f"\nCaptured screenshot: {screenshot_path}")

        print("\nCONSOLE LOGS:")
        for log in console_logs:
            if any(k in log.lower() for k in ["pdf", "worker", "study", "error", "warn"]):
                print(log)

        print("\nNETWORK LOGS RELATED TO PDF / WORKER:")
        for net in network_logs:
            if any(k in net.lower() for k in ["pdf", "worker", "doc_a3b336"]):
                print(net)

        browser.close()

if __name__ == "__main__":
    test_integrated()
