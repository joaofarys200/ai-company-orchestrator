import asyncio
import os
import sys
import time
import json
import urllib.request
import hashlib
from playwright.async_api import async_playwright

sys.path.insert(0, os.path.abspath(os.getcwd()))
from services.study_service import StudyService

async def run_investigation():
    print("=" * 70)
    print("FINAL FORENSIC INVESTIGATION — DEEP RUNTIME INSPECTION")
    print("=" * 70)

    # 1. Inspect Backend Servers and Document
    service = StudyService(workspace_root=os.getcwd())
    target_doc_id = "doc_a3b336f4295d"
    backend_doc = service.get_document(target_doc_id)
    assert backend_doc is not None, f"Document {target_doc_id} not found in backend!"

    file_path = backend_doc.metadata.get("file_path")
    assert file_path and os.path.exists(file_path), f"File {file_path} not found on disk!"

    with open(file_path, "rb") as f:
        backend_bytes = f.read()
    backend_hash = hashlib.sha256(backend_bytes).hexdigest()
    print(f"[BACKEND DOC] ID: {target_doc_id}")
    print(f"[BACKEND DOC] File: {file_path}")
    print(f"[BACKEND DOC] Size: {len(backend_bytes)} bytes")
    print(f"[BACKEND DOC] SHA256: {backend_hash}")
    print(f"[BACKEND DOC] Page count: {backend_doc.page_count}")

    # Create debug directory for artifacts
    debug_dir = os.path.join(os.getcwd(), "docs", "debug")
    os.makedirs(debug_dir, exist_ok=True)

    async with async_playwright() as p:
        print("\nLaunching Microsoft Edge (channel='msedge')...")
        browser = await p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--no-sandbox", "--disable-gpu"]
        )
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        console_logs = []
        network_logs = []
        page.on("console", lambda msg: console_logs.append({"type": msg.type, "text": msg.text}))
        page.on("request", lambda req: network_logs.append({"method": req.method, "url": req.url}))
        page.on("response", lambda res: network_logs.append({
            "status": res.status,
            "url": res.url,
            "contentType": res.headers.get("content-type", ""),
            "contentLength": res.headers.get("content-length", "")
        }))

        print("\nNavigating to http://localhost:8000/ ...")
        await page.goto("http://localhost:8000/", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # Record frontend bundle details from the page
        bundle_info = await page.evaluate("""() => {
            const scripts = Array.from(document.querySelectorAll('script')).map(s => s.src || s.innerHTML.substring(0, 50));
            const links = Array.from(document.querySelectorAll('link')).map(l => l.href);
            return {
                url: window.location.href,
                origin: window.location.origin,
                scripts,
                links,
                title: document.title
            };
        }""")
        print("\n[FRONTEND INSTANCE AUDIT]")
        print(f"URL: {bundle_info['url']}")
        print(f"Origin: {bundle_info['origin']}")
        print(f"Title: {bundle_info['title']}")
        print(f"Scripts: {bundle_info['scripts']}")
        print(f"Links: {bundle_info['links']}")

        # Open Dev panel if collapsed
        dev_btn = page.locator("button[title*='Painel Dev'], button[title*='Terminal']").first
        if await dev_btn.count() > 0 and await dev_btn.is_visible():
            await dev_btn.click()
            await page.wait_for_timeout(1000)

        # Switch to Estudo tab
        print("\nNavigating to Estudo tab...")
        await page.locator("#workspace-tab-study, [data-testid='tab-study']").first.click()
        await page.wait_for_timeout(2000)

        # Switch to Library
        library_btn = page.locator("#study-nav-library-btn")
        if await library_btn.count() > 0 and await library_btn.is_visible():
            await library_btn.first.click()
            await page.wait_for_timeout(1500)

        # Find document card in library
        print("\nLocating document card in library...")
        card = page.locator(f"div.group:has-text('Predicting performance online consumer reviews')").first
        assert await card.count() > 0, "Document card not found in library!"

        # Click document title to open reader
        print("Clicking document title to enter StudyReaderView...")
        title_btn = card.locator("h2").first
        await title_btn.click()
        
        # Wait 4 seconds for render
        await page.wait_for_timeout(4000)

        # Check visual state: Loading spinner
        spinner_locator = page.locator("text='A carregar o artigo científico em alta resolução...'")
        is_spinner_visible = await spinner_locator.count() > 0 and await spinner_locator.first.is_visible()
        print(f"\n[SPINNER CHECK] 'A carregar o artigo científico...' is visible: {is_spinner_visible}")

        reload_btn = page.locator("button:has-text('Recarregar documento')")
        is_reload_btn_visible = await reload_btn.count() > 0 and await reload_btn.first.is_visible()
        print(f"[RELOAD BTN CHECK] 'Recarregar documento' is visible: {is_reload_btn_visible}")

        error_banner = page.locator("text='Aviso de Leitura do Ficheiro'")
        is_error_banner_visible = await error_banner.count() > 0 and await error_banner.first.is_visible()
        print(f"[ERROR BANNER CHECK] 'Aviso de Leitura do Ficheiro' is visible: {is_error_banner_visible}")

        # Check PDF page containers
        page_containers = page.locator("div[id^='pdf-page-']")
        container_count = await page_containers.count()
        print(f"[PAGE CONTAINERS CHECK] div[id^='pdf-page-'] count: {container_count}")

        # Deep Canvas #pdf-page-1 Inspection
        canvas_locator = page.locator("#pdf-page-1 canvas")
        canvas_count = await canvas_locator.count()
        print(f"[PAGE 1 CANVAS CHECK] #pdf-page-1 canvas count: {canvas_count}")

        canvas_data = None
        if canvas_count > 0:
            canvas = canvas_locator.first
            canvas_data = await page.evaluate("""() => {
                const c = document.querySelector('#pdf-page-1 canvas');
                if (!c) return null;
                const rect = c.getBoundingClientRect();
                const style = window.getComputedStyle(c);
                const parent = c.parentElement;
                const parentStyle = parent ? window.getComputedStyle(parent) : null;
                const parentRect = parent ? parent.getBoundingClientRect() : null;

                // elementFromPoint test at center
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;
                const topElement = document.elementFromPoint(cx, cy);

                // Pixel test via getImageData
                let nonZeroPixels = 0;
                let totalPixels = 0;
                try {
                    const ctx = c.getContext('2d');
                    if (ctx) {
                        const img = ctx.getImageData(0, 0, Math.min(c.width, 200), Math.min(c.height, 200));
                        totalPixels = img.data.length / 4;
                        for (let i = 0; i < img.data.length; i += 4) {
                            if (img.data[i] !== 255 || img.data[i+1] !== 255 || img.data[i+2] !== 255 || img.data[i+3] !== 0) {
                                if (img.data[i+3] > 0 && (img.data[i] < 250 || img.data[i+1] < 250 || img.data[i+2] < 250)) {
                                    nonZeroPixels++;
                                }
                            }
                        }
                    }
                } catch (e) {
                    nonZeroPixels = -1;
                }

                return {
                    width: c.width,
                    height: c.height,
                    styleWidth: style.width,
                    styleHeight: style.height,
                    display: style.display,
                    visibility: style.visibility,
                    opacity: style.opacity,
                    position: style.position,
                    zIndex: style.zIndex,
                    rect: {
                        x: rect.x, y: rect.y, width: rect.width, height: rect.height,
                        top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right
                    },
                    parentTag: parent ? parent.tagName : null,
                    parentId: parent ? parent.id : null,
                    parentRect: parentRect ? {
                        x: parentRect.x, y: parentRect.y, width: parentRect.width, height: parentRect.height
                    } : null,
                    elementFromPoint: topElement ? {
                        tag: topElement.tagName,
                        id: topElement.id,
                        className: topElement.className
                    } : null,
                    nonZeroPixels,
                    totalPixels
                };
            }""")
            print(f"[CANVAS METRICS]:\n{json.dumps(canvas_data, indent=2)}")

            # Screenshot Page 1 Canvas directly
            canvas_ss_path = os.path.join(debug_dir, "pdf_page1_canvas.png")
            await canvas.screenshot(path=canvas_ss_path)
            print(f"Captured canvas screenshot: {canvas_ss_path}")

            # Screenshot Page 1 Container directly
            container = page.locator("#pdf-page-1").first
            container_ss_path = os.path.join(debug_dir, "pdf_page1_container.png")
            await container.screenshot(path=container_ss_path)
            print(f"Captured container screenshot: {container_ss_path}")

        # Capture full viewport screenshot
        full_ss_path = os.path.join(debug_dir, "user_visible_study_reader.png")
        await page.screenshot(path=full_ss_path)
        print(f"Captured full UI screenshot: {full_ss_path}")

        # Filter and print relevant console logs
        print("\n[BROWSER CONSOLE LOGS]")
        for l in console_logs:
            if any(k in l['text'].lower() for k in ['pdf', 'worker', 'study', 'error', 'warn', 'load']):
                print(f"[{l['type'].upper()}] {l['text']}")

        # Filter and print relevant network requests
        print("\n[RELEVANT NETWORK LOGS]")
        for n in network_logs:
            url = n.get('url', '')
            if any(k in url.lower() for k in ['pdf', 'worker', 'file', 'study', 'assets']):
                print(f"{n}")

        await browser.close()
        print("\nINVESTIGATION COMPLETE.")

if __name__ == "__main__":
    asyncio.run(run_investigation())
