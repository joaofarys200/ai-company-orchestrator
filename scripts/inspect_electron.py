import time
from playwright.sync_api import sync_playwright

def inspect():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        print("Connected to Electron over CDP!")
        context = browser.contexts[0]
        page = context.pages[0]
        print(f"Page title: {page.title()}")
        print(f"Page URL: {page.url}")
        
        # Check console logs from Electron page
        page.on("console", lambda m: print(f"[ELECTRON CONSOLE {m.type}] {m.text}"))
        page.on("pageerror", lambda e: print(f"[ELECTRON EXCEPTION] {e}"))
        
        print("Reloading page to get latest build...")
        page.goto("http://localhost:8000/", wait_until="networkidle")
        time.sleep(2)
        
        # Open Dev panel if collapsed
        dev_btn = page.locator("button[title*='Painel Dev'], button[title*='Terminal']").first
        if dev_btn.is_visible():
            print("Opening Dev panel...")
            dev_btn.click()
            time.sleep(1)
            
        print("Clicking Estudo tab...")
        page.locator("#workspace-tab-study, [data-testid='tab-study']").first.click()
        time.sleep(1.5)
        
        print("Clicking Predicting performance document...")
        page.locator("h2:has-text('Predicting performance online consumer reviews')").first.click()
        
        print("Waiting 6 seconds in StudyReaderView...")
        time.sleep(6)
        
        spinner = page.locator("text='A carregar o artigo científico em alta resolução...'").first
        print(f"Spinner visible in Electron: {spinner.is_visible()}")
        
        canvases = page.locator("div[id^='pdf-page-'] canvas")
        print(f"Canvas count in Electron: {canvases.count()}")
        
        if canvases.count() > 0:
            c = canvases.first
            print(f"Canvas 1 bounding box: {c.bounding_box()}")
            meta = page.evaluate("""() => {
                const canvas = document.querySelector("#pdf-page-1 canvas");
                let nonZero = 0;
                if (canvas) {
                    const ctx = canvas.getContext('2d');
                    const img = ctx.getImageData(0, 0, Math.min(canvas.width, 200), Math.min(canvas.height, 200));
                    for (let i = 0; i < img.data.length; i += 4) {
                        if (img.data[i] !== 255 || img.data[i+1] !== 255 || img.data[i+2] !== 255) {
                            nonZero++;
                        }
                    }
                }
                return {
                    buildId: window.__JARVIS_BUILD_ID__,
                    lifecycle: window.__JARVIS_PDF_LIFECYCLE__ ? window.__JARVIS_PDF_LIFECYCLE__() : null,
                    canvasW: canvas?.width,
                    canvasH: canvas?.height,
                    nonZero
                };
            }""")
            print("Render evaluation:", meta)
            
        screenshot_path = "docs/debug/electron_real_reader_polyfilled.png"
        page.screenshot(path=screenshot_path)
        print(f"Captured screenshot to {screenshot_path}")

if __name__ == "__main__":
    inspect()
