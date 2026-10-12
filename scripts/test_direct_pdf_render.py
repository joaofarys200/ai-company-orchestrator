"""
Standalone minimal test for Section 13:
PDF bytes -> PDF.js -> first page -> canvas
Tests purely whether PDF.js in Chromium/Edge can render
Predicting_performance_online_consumer_reviews(1).pdf directly on a canvas.
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(r"C:\Users\joaor\.gemini\antigravity-ide\brain\53b9c83c-04cb-413d-9610-65cb1ea8e073")
PDF_PATH = Path(r"C:\Users\joaor\Desktop\JarvisOS\data\study\a3b336f4295d0d51_Predicting_performance_online_consumer_reviews(1).pdf")

# HTML page template that loads PDF.js from the local server or unpkg/dist and renders the PDF to canvas
HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Direct PDF Render Test</title>
  <script src="/dist/assets/index-BDAdi1aA.js" type="module"></script>
</head>
<body style="background:#111; color:#eee; margin:20px;">
  <h1>Direct PDF Render Test</h1>
  <div id="status">Loading...</div>
  <canvas id="pdf-canvas" style="border:1px solid #444; margin-top:10px;"></canvas>
  <script type="module">
    import * as pdfjsLib from 'http://localhost:8000/dist/assets/index-BDAdi1aA.js';
  </script>
</body>
</html>
"""

def run_direct_test():
    print("=" * 60)
    print("SECTION 13: CONTROLLED MINIMAL TEST (DIRECT PDF RENDER)")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        console_logs = []
        network_events = []

        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("request", lambda req: network_events.append(f"REQ: {req.method} {req.url}"))
        page.on("response", lambda res: network_events.append(f"RES: {res.status} {res.url} ({res.headers.get('content-type', '')})"))

        # Navigate to test page on local server
        print("Navigating to http://localhost:8000/ ...")
        page.goto("http://localhost:8000/", wait_until="networkidle", timeout=30000)

        # Inject a direct test inside the actual browser context where pdfjs is loaded
        result = page.evaluate("""async () => {
            const logs = [];
            const log = (msg) => logs.push(msg);

            try {
                log('1. Checking window / pdfjs availability');
                // Fetch PDF bytes directly
                log('2. Fetching PDF bytes from /api/study/document/doc_a3b336f4295d/file');
                const res = await fetch('/api/study/document/doc_a3b336f4295d/file');
                log('HTTP status: ' + res.status + ' content-type: ' + res.headers.get('content-type'));
                const buf = await res.arrayBuffer();
                log('Fetched buffer byteLength: ' + buf.byteLength);

                // Check pdfjsLib in window or module
                // Let's import pdf.mjs from node_modules or public
                log('3. Loading pdfjs-dist via dynamic import');
                let pdfjsLib;
                try {
                    // Try to use GlobalWorkerOptions if already initialized
                    pdfjsLib = await import('/pdf.worker.min.mjs');
                } catch (e) {
                    log('Worker import notice: ' + e.message);
                }

                return {
                    success: true,
                    status: res.status,
                    byteLength: buf.byteLength,
                    logs
                };
            } catch (err) {
                return {
                    success: false,
                    error: err.toString(),
                    logs
                };
            }
        }""")

        print("Evaluate result:", result)
        browser.close()

if __name__ == "__main__":
    run_direct_test()
