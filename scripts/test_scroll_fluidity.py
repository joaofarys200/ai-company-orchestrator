import time
from playwright.sync_api import sync_playwright

def test_scroll():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto('http://localhost:8000/', wait_until='networkidle')
        time.sleep(2)
        
        # Open DevPanel
        dev_btn = page.locator("button[title*='Painel Dev'], button[title*='Abrir Painel Dev']").first
        if dev_btn.count() > 0 and dev_btn.is_visible():
            dev_btn.click()
            time.sleep(1.5)
            
        # Switch to Estudo tab
        study_btn = page.locator('#workspace-tab-study, [data-testid="tab-study"], button:has-text("Estudo")').first
        if study_btn.count() > 0 and study_btn.is_visible():
            study_btn.click(force=True)
            time.sleep(1.5)
        else:
            page.evaluate("() => { if (window.__setActiveTab) window.__setActiveTab('study'); }")
            time.sleep(1.5)
            
        doc_btn = page.locator("h2:has-text('Predicting performance online consumer reviews'), button:has-text('Ler')").first
        doc_btn.click(force=True)
        time.sleep(4)
        
        # Now perform continuous scrolling through the document
        scroll_container = page.locator(".pdf-reader-scroll-container").first
        print("Starting smooth scroll test...")
        
        scroll_start = time.time()
        for i in range(1, 12):
            page.evaluate(f"""(step) => {{
                const el = document.querySelector('.pdf-reader-scroll-container');
                if (el) {{
                    el.scrollTop = step * 1000;
                }}
            }}""", i)
            time.sleep(0.3)
            
        scroll_duration = time.time() - scroll_start
        print(f"Scrolled through all pages in {scroll_duration:.2f} seconds.")
        
        # Verify page 5 and page 11 rendered
        rendered_count = page.evaluate("""() => {
            const canvases = document.querySelectorAll('.pdf-page-container canvas');
            let count = 0;
            canvases.forEach(c => {
                if (c.width > 0 && c.height > 0) count++;
            });
            return {
                totalContainers: document.querySelectorAll('.pdf-page-container').length,
                renderedCanvases: count,
                currentScrollTop: document.querySelector('.pdf-reader-scroll-container')?.scrollTop
            };
        }""")
        print("RENDERED PAGES STATUS:", rendered_count)
        
        page.screenshot(path="docs/debug/scroll_fluidity_test.png")
        print("Captured scroll_fluidity_test.png")
        browser.close()

if __name__ == '__main__':
    test_scroll()
