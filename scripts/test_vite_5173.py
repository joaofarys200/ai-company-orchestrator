import time
from playwright.sync_api import sync_playwright

def test():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()
        page.on("console", lambda m: print(f"[{m.type}] {m.text}", flush=True))
        page.on("pageerror", lambda e: print(f"[PAGE ERROR] {e}", flush=True))
        print("Navigating to http://localhost:5173/...", flush=True)
        page.goto("http://localhost:5173/", wait_until="networkidle")
        time.sleep(2)
        dev_btn = page.locator("button[title*='Painel Dev'], button[title*='Terminal']").first
        if dev_btn.is_visible():
            dev_btn.click()
            time.sleep(1)
        page.locator("#workspace-tab-study, [data-testid='tab-study']").first.click()
        time.sleep(1.5)
        page.locator("h2:has-text('Predicting performance online consumer reviews')").first.click()
        print("Waiting 6 seconds in StudyReaderView on port 5173...", flush=True)
        time.sleep(6)
        spinner = page.locator("text='A carregar o artigo científico em alta resolução...'").first
        print(f"Spinner visible: {spinner.is_visible()}", flush=True)
        canvases = page.locator("div[id^='pdf-page-'] canvas")
        print(f"Canvas count: {canvases.count()}", flush=True)
        if canvases.count() > 0:
            c = canvases.first
            box = c.bounding_box()
            print(f"Canvas 1 bounding box: {box}", flush=True)
        browser.close()

if __name__ == "__main__":
    test()
