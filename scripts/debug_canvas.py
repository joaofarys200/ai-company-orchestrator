import asyncio
import sys
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel='msedge', headless=True)
        page = await b.new_page()
        logs = []
        page.on('console', lambda m: print(f"[{m.type}] {m.text}", flush=True))
        page.on('pageerror', lambda e: print(f"[EXCEPTION] {e}", flush=True))
        
        print("Navigating to http://localhost:8000/...", flush=True)
        await page.goto('http://localhost:8000/', wait_until='networkidle')
        await page.wait_for_timeout(1000)
        
        # Open Dev panel if collapsed
        dev_btn = page.locator("button[title*='Painel Dev'], button[title*='Terminal']").first
        if await dev_btn.count() > 0 and await dev_btn.is_visible():
            await dev_btn.click()
            await page.wait_for_timeout(1000)
        
        study_tab = page.locator('#workspace-tab-study, [data-testid=\"tab-study\"]').first
        await study_tab.click()
        await page.wait_for_timeout(1000)
        
        lib_btn = page.locator('#study-nav-library-btn').first
        if await lib_btn.count() > 0 and await lib_btn.is_visible():
            await lib_btn.click()
            await page.wait_for_timeout(1000)
            
        card = page.locator("div.group:has-text('Predicting performance online consumer reviews')").first
        await card.locator("h2").first.click()
        print('Waiting 10 seconds in StudyReaderView...', flush=True)
        await page.wait_for_timeout(10000)
            
        meta = await page.evaluate('''() => {
            const canvas = document.querySelector('#pdf-page-1 canvas');
            let nonZero = 0;
            if (canvas) {
                try {
                    const ctx = canvas.getContext('2d');
                    const img = ctx.getImageData(0, 0, Math.min(canvas.width, 250), Math.min(canvas.height, 250));
                    for (let i = 0; i < img.data.length; i += 4) {
                        if (img.data[i+3] > 0 && (img.data[i] < 245 || img.data[i+1] < 245 || img.data[i+2] < 245)) {
                            nonZero++;
                        }
                    }
                } catch (e) {
                    nonZero = -999;
                }
            }
            const spinner = document.querySelector('.animate-spin');
            return {
                lifecycle: window.__JARVIS_PDF_LIFECYCLE__ ? window.__JARVIS_PDF_LIFECYCLE__() : null,
                canvasW: canvas?.width,
                canvasH: canvas?.height,
                nonZero,
                spinnerVisible: Boolean(spinner && window.getComputedStyle(spinner).display !== 'none'),
                spansCount: document.querySelectorAll('#pdf-page-1 .textLayer span').length
            };
        }''')
        print('\n=== DOM & RENDER METRICS ===', flush=True)
        print(meta, flush=True)
        await b.close()

asyncio.run(run())
