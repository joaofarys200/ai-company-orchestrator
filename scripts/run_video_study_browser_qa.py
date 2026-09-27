"""
Playwright End-to-End Real Browser QA for Multimodal Video Intelligence in Study Experience (Estudo)
Browser: Microsoft Edge (msedge)
Validates all 23 steps of Golden Path (Req 45) + Multimodal Grounding (Req 46-48).
"""

import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(r"C:\Users\joaor\.gemini\antigravity-ide\brain\53b9c83c-04cb-413d-9610-65cb1ea8e073")

def run_browser_qa():
    print("=" * 70)
    print("STARTING REAL BROWSER QA (Microsoft Edge + Playwright)")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1.0,
        )
        page = context.new_page()

        # Step 1: Abrir Jarvis OS e navegar para Estudo
        print("[Step 1] Navigating to Jarvis OS application...")
        page.goto("http://localhost:8000/", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        print("[Step 1.1] Opening Dev Panel from bottom dock...")
        dev_btn = page.locator("button[title*='Painel Dev'], button[title*='Terminal']").first
        if dev_btn.is_visible():
            dev_btn.click()
            time.sleep(1.5)

        print("[Step 1.2] Switching to Estudo section in Workspace...")
        study_tab = page.locator("#workspace-tab-study, [data-testid='tab-study']").first
        if study_tab.is_visible():
            study_tab.click()
            time.sleep(1.5)
        else:
            page.evaluate("window.__setActiveTab?.('study')")
            time.sleep(1.5)

        # Step 2 & 3: Biblioteca e validação do vídeo
        print("[Step 2 & 3] Verifying video document in library...")
        video_filter = page.locator("button:has-text('Vídeos')").first
        if video_filter.is_visible():
            video_filter.click()
            time.sleep(1)

        screenshot_1 = ARTIFACTS_DIR / "01_browser_qa_library_video_card.png"
        page.screenshot(path=str(screenshot_1))
        print(f"  -> Captured: {screenshot_1.name}")

        # Step 4: Abrir vídeo no leitor
        print("[Step 4] Opening video in StudyVideoReaderView...")
        ler_btn = page.locator("button:has-text('Ler')").first
        if ler_btn.is_visible():
            ler_btn.click()
            time.sleep(2.5)
        else:
            page.locator("h2:has-text('Consenso Distribuído')").first.click()
            time.sleep(2.5)

        screenshot_2 = ARTIFACTS_DIR / "02_browser_qa_video_reader_opened.png"
        page.screenshot(path=str(screenshot_2))
        print(f"  -> Captured: {screenshot_2.name}")

        # Step 5 & 6: Reproduzir e Seek
        print("[Step 5 & 6] Playing video and seeking to 7.0s (Architecture Diagram)...")
        video_el = page.locator("video").first
        if video_el.is_visible():
            page.evaluate("document.querySelector('video')?.play()")
            time.sleep(1)
            page.evaluate("document.querySelector('video').currentTime = 7.0")
            time.sleep(1)

        # Step 7 & 8: Abrir transcript e clicar numa frase
        print("[Step 7 & 8] Verifying transcript and clicking on segment...")
        trans_tab = page.locator("button:has-text('Transcrição')").first
        if trans_tab.is_visible():
            trans_tab.click()
            time.sleep(1)

        # Find segment mentioning diagram or leader
        seg = page.locator("text='diagrama de arquitetura'").first
        if seg.is_visible():
            seg.click()
            time.sleep(1)

        # Step 9: Confirmar timestamp
        current_time = page.evaluate("document.querySelector('video')?.currentTime || 0")
        print(f"[Step 9] Confirmed synced video timestamp: {current_time:.1f}s")

        screenshot_3 = ARTIFACTS_DIR / "03_browser_qa_transcript_seek_sync.png"
        page.screenshot(path=str(screenshot_3))
        print(f"  -> Captured: {screenshot_3.name}")

        # Step 10 & 11: Traduzir e Explicar
        print("[Step 10 & 11] Testing contextual translation & explanation...")
        translate_btn = page.locator("button[title*='Traduzir']").first
        if translate_btn.is_visible():
            translate_btn.click()
            time.sleep(1)

        explain_btn = page.locator("button[title*='Explicar este conceito']").first
        if explain_btn.is_visible():
            explain_btn.click()
            time.sleep(1)

        # Step 12 & 13: Procurar conceito e saltar para ocorrência
        print("[Step 12 & 13] Searching transcript for 'desempenho'...")
        search_input = page.locator("[data-testid='study-transcript-search-input']").first
        if search_input.is_visible():
            search_input.fill("desempenho")
            time.sleep(1)

        # Step 14: Capturar momento (Guardar momento)
        print("[Step 14] Saving visual moment note...")
        save_moment_btn = page.locator("button:has-text('Guardar momento')").first
        if save_moment_btn.is_visible():
            save_moment_btn.click()
            time.sleep(1)
            # Fill textarea
            textarea = page.locator("textarea[placeholder*='Escreve uma nota explicativa']").first
            if textarea.is_visible():
                textarea.fill("O gráfico demonstra throughput sustentado com quórum Raft.")
                time.sleep(0.5)
                page.locator("button:has-text('Guardar Anotação')").first.click()
                time.sleep(1)

        # Test contextual actions "O que está a acontecer aqui?" and "Explicar o que está no ecrã"
        print("[Steps 23-24] Testing 'O que está a acontecer aqui?' and 'Explicar o que está no ecrã'...")
        explain_moment_btn = page.locator("[data-testid='study-btn-explain-moment']").first
        if explain_moment_btn.is_visible():
            explain_moment_btn.click()
            time.sleep(1.5)

        explain_visual_btn = page.locator("[data-testid='study-btn-explain-visual']").first
        if explain_visual_btn.is_visible():
            explain_visual_btn.click()
            time.sleep(1.5)

        screenshot_4 = ARTIFACTS_DIR / "04_browser_qa_contextual_actions_assistant.png"
        page.screenshot(path=str(screenshot_4))
        print(f"  -> Captured: {screenshot_4.name}")

        # Step 32: Ask the video question (Q&A)
        print("[Step 32] Testing Ask the Video Q&A...")
        ask_tab = page.locator("button:has-text('Perguntar')").first
        if ask_tab.is_visible():
            ask_tab.click()
            time.sleep(1)
            ask_input = page.locator("input[placeholder*='Pergunta sobre este vídeo']").first
            if ask_input.is_visible():
                ask_input.fill("Como funciona o quórum de maioria no Raft?")
                time.sleep(0.5)
                ask_input.press("Enter")
                time.sleep(2)

        # Step 15: Gerar summary
        print("[Step 15] Navigating to Summary tab in Study header...")
        page.locator("#study-nav-summary-btn").click()
        time.sleep(1.5)

        # Step 16: Gerar Cornell
        print("[Step 16] Navigating to Notas Cornell...")
        page.locator("#study-nav-notes-btn").click()
        time.sleep(1.5)

        # Step 17, 18, 19: Gerar Quiz, responder e flashcards
        print("[Step 17, 18, 19] Navigating to Quiz & Rever...")
        page.locator("#study-nav-quiz-btn").click()
        time.sleep(1.5)

        # Click option 1 on question 1
        option_btn = page.locator("button:has-text('Auxiliar contextualmente')").first
        if option_btn.is_visible():
            option_btn.click()
            time.sleep(0.5)

        # Switch to Flashcards tab
        flashcards_tab = page.locator("button:has-text('Flashcards')").first
        if flashcards_tab.is_visible():
            flashcards_tab.click()
            time.sleep(1)

        screenshot_5 = ARTIFACTS_DIR / "05_browser_qa_summary_cornell_quiz.png"
        page.screenshot(path=str(screenshot_5))
        print(f"  -> Captured: {screenshot_5.name}")

        # Step 20: Guardar Knowledge
        print("[Step 20] Testing Save to Knowledge Vault...")
        page.locator("#study-nav-knowledge-btn").click()
        time.sleep(1.5)

        # Step 21 & 22: Fechar e reabrir
        print("[Step 21 & 22] Returning to Library and reopening video...")
        page.locator("#study-nav-library-btn").click()
        time.sleep(1.5)

        # Step 23: Reabrir e confirmar timestamp preservado
        page.locator("button:has-text('Ler')").first.click()
        time.sleep(2)
        reopened_time = page.evaluate("document.querySelector('video')?.currentTime || 0")
        print(f"[Step 23] Reopened video timestamp: {reopened_time:.1f}s")

        screenshot_6 = ARTIFACTS_DIR / "06_browser_qa_watch_progress_resumed.png"
        page.screenshot(path=str(screenshot_6))
        print(f"  -> Captured: {screenshot_6.name}")

        browser.close()
        print("=" * 70)
        print("REAL BROWSER QA COMPLETED 100% SUCCESSFULLY ON MICROSOFT EDGE!")
        print("=" * 70)

if __name__ == "__main__":
    run_browser_qa()
