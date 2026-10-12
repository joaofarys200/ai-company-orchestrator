import time
from playwright.sync_api import sync_playwright

def verify():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto('http://localhost:8000/', wait_until='networkidle')
        time.sleep(2)
        
        # Open DevPanel if present
        dev_btn = page.locator("button[title*='Painel Dev'], button[title*='Abrir Painel Dev'], button[title*='Terminal']").first
        if dev_btn.count() > 0 and dev_btn.is_visible():
            print("Opening Dev panel...")
            dev_btn.click()
            time.sleep(1.5)
            
        # Switch to Estudo tab
        study_btn = page.locator('#workspace-tab-study, [data-testid="tab-study"], button:has-text("Estudo")').first
        if study_btn.count() > 0 and study_btn.is_visible():
            print("Clicking Estudo tab...")
            study_btn.click(force=True)
            time.sleep(1.5)
        else:
            page.evaluate("() => { if (window.__setActiveTab) window.__setActiveTab('study'); }")
            time.sleep(1.5)
            
        print("Clicking Predicting performance document...")
        doc_btn = page.locator("h2:has-text('Predicting performance online consumer reviews'), button:has-text('Ler')").first
        doc_btn.click(force=True)
        time.sleep(5)
        
        res = page.evaluate('''() => {
            const buildId = window.__JARVIS_BUILD_ID__;
            const canvas = document.querySelector('#pdf-page-1 canvas');
            const textSpan = document.querySelector('#pdf-page-1 .textLayer span');
            let spanColor = null;
            if (textSpan) {
                spanColor = window.getComputedStyle(textSpan).color;
            }
            return {
                buildId,
                canvasW: canvas?.width,
                canvasH: canvas?.height,
                canvasStyleW: canvas?.style.width,
                canvasStyleH: canvas?.style.height,
                spanColor
            };
        }''')
        print("EVALUATION:", res)
        page.screenshot(path="docs/debug/verified_v8_hidpi_sharp.png")
        print("Screenshot saved to docs/debug/verified_v8_hidpi_sharp.png")
        browser.close()

if __name__ == '__main__':
    verify()
