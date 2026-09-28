import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.getcwd()))
from services.study_service import StudyService
from playwright.async_api import async_playwright

async def main():
    service = StudyService(workspace_root=os.getcwd())
    # Ingest a temporary test item for deletion testing
    dummy_text = "This is a temporary test document to verify the deletion flow in Study Library."
    doc = service.ingest_document(
        file_path_or_content=dummy_text.encode('utf-8'),
        filename="dummy_doc_delete_test.txt",
        subject="Engenharia de Software",
        source_type="TXT",
        custom_title="Documento de Teste para Eliminação",
    )
    test_doc_id = doc.document_id
    print(f"Created temporary doc: {test_doc_id} ('{doc.title}')")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--no-sandbox", "--disable-gpu"]
        )
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("Navigating to Jarvis OS...")
        await page.goto("http://localhost:8000", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # Open Dev panel if collapsed
        dev_btn = page.locator("button[title*='Painel Dev'], button[title*='Terminal']").first
        if await dev_btn.count() > 0 and await dev_btn.is_visible():
            await dev_btn.click()
            await page.wait_for_timeout(1000)

        # Open study tab
        print("Opening Estudo tab...")
        await page.locator("#workspace-tab-study, [data-testid='tab-study']").first.click()
        await page.wait_for_timeout(2000)

        # Switch to library tab if inside reader
        library_btn = page.locator("#study-nav-library-btn")
        if await library_btn.count() > 0 and await library_btn.is_visible():
            await library_btn.first.click()
            print("Clicked Biblioteca tab")
        await page.wait_for_timeout(1500)

        # Refresh study documents via window.__jarvisRefreshStudy
        print("Refreshing study documents...")
        await page.evaluate("() => { if (window.__jarvisRefreshStudy) window.__jarvisRefreshStudy(); }")
        await page.wait_for_timeout(2000)

        # Look for the card with "Documento de Teste para Eliminação"
        card = page.locator("div.group:has-text('Documento de Teste para Eliminação')")
        card_count = await card.count()
        print(f"Found cards matching test doc: {card_count}")
        assert card_count > 0, "Test card must be visible in Study Library"

        # Find trash button on this card
        trash_btn = card.first.locator("button[title='Eliminar material da biblioteca']")
        assert await trash_btn.count() > 0, "Delete button must exist on the card"
        await trash_btn.first.click()
        print("Clicked trash button")
        await page.wait_for_timeout(1000)

        # Verify confirmation modal is open
        modal = page.locator("div:has-text('Eliminar Material de Estudo')")
        assert await modal.count() > 0, "Delete confirmation modal must be open"
        print("Delete confirmation modal is visible")

        # Capture modal screenshot
        os.makedirs("evidence/study", exist_ok=True)
        await page.screenshot(path="evidence/study/07_study_library_delete_modal.png")
        print("Captured modal screenshot: evidence/study/07_study_library_delete_modal.png")

        # Click 'Eliminar Definitivamente'
        confirm_btn = page.locator("button:has-text('Eliminar Definitivamente')")
        assert await confirm_btn.count() > 0, "Confirm delete button must exist"
        await confirm_btn.first.click()
        print("Clicked 'Eliminar Definitivamente'")
        await page.wait_for_timeout(2000)

        # Verify card is gone
        card_count_after = await page.locator("div.group:has-text('Documento de Teste para Eliminação')").count()
        print(f"Card count after deletion: {card_count_after}")
        assert card_count_after == 0, "Card must no longer exist in the UI"

        # Verify backend deleted it
        service_check = StudyService(workspace_root=os.getcwd())
        doc_in_backend = service_check.get_document(test_doc_id)
        print(f"Doc in backend after deletion: {doc_in_backend}")
        assert doc_in_backend is None, "Document must be removed from backend"

        await page.screenshot(path="evidence/study/08_study_library_after_delete.png")
        print("Captured after-delete screenshot: evidence/study/08_study_library_after_delete.png")

        print("TEST_DELETE_DOCUMENT_FLOW = PASS")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
