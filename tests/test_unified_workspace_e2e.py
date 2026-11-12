import functools
import http.server
import json
import os
import socketserver
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


DIST_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def dist_server():
    if not (DIST_DIR / "index.html").is_file():
        pytest.skip("frontend/dist not built; run npm run build in frontend/")
    handler = functools.partial(QuietHandler, directory=str(DIST_DIR))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{port}"
        finally:
            httpd.shutdown()


def test_unified_split_workspace_e2e(dist_server):
    pdf_doc = {
        "document_id": "doc_pdf_test",
        "title": "Resumo Completo — Gestão de Projetos",
        "source_type": "PDF",
        "subject": "Gestão",
        "language": "pt",
        "page_count": 12,
        "sections": [
            {
                "section_id": "sec_1",
                "title": "Estimar Recursos (ISO 21500 Tab. 16)",
                "page_start": 1,
                "page_end": 2,
                "text": "Conteúdo académico completo sobre estimativa de recursos em projetos.",
            }
        ],
        "extracted_text": "Conteúdo académico completo sobre estimativa de recursos em projetos.",
        "metadata": {
            "generation_mode": "EXTRACTIVE_GROUNDED",
            "unavailable_generative_features": [
                "interpretive_synthesis",
                "causal_inference",
            ],
            "summaries": {
                "quick": [
                    "Estimar Recursos determina pessoas, equipamentos e infraestruturas necessárias (ISO 21500)."
                ],
                "study": [
                    {
                        "title": "Estimar Recursos (ISO 21500 Tab. 16)",
                        "page": 1,
                        "summary": "Determina os recursos necessários para cada atividade do projeto.",
                        "concepts": ["RBS", "ISO 21500"],
                    }
                ],
                "detailed": [
                    {
                        "title": "Estimar Recursos (ISO 21500 Tab. 16)",
                        "text": "Detalhamento de tipos, quantidades e disponibilidade temporal.",
                    }
                ],
                "exam": {
                    "high_yield_concepts": [{"concept": "RBS", "detail": "Resource Breakdown Structure"}],
                    "likely_questions": [{"question": "O que define a RBS?", "answer": "Estrutura hierárquica de recursos."}],
                },
            },
        },
        "reading_progress": {"current_page": 1, "progress_percent": 10},
    }

    video_doc = {
        "document_id": "doc_vid_test",
        "title": "000 Planning Part III (Communication)",
        "source_type": "VIDEO",
        "subject": "Gestão",
        "language": "en",
        "page_count": 1,
        "sections": [],
        "extracted_text": "Techniques & Tools Plan communications Project managers spend most of their time communicating.",
        "metadata": {
            "asr_unavailable_reason": "WHISPER_NOT_INSTALLED",
            "ocr_status": "OCR_COMPLETED",
            "video": {
                "duration_seconds": 567.36,
                "asr_unavailable_reason": "WHISPER_NOT_INSTALLED",
                "ocr_status": "OCR_COMPLETED",
                "transcript_segments": [],
                "chapters": [],
                "keyframes": [
                    {
                        "frame_id": "frame_006",
                        "timestamp": 95.06,
                        "timestamp_str": "01:35",
                        "is_slide": True,
                        "ocr_text": "Techniques & Tools: Plan communications - Project managers spend time communicating.",
                    }
                ],
            },
        },
        "reading_progress": {"current_page": 1, "progress_percent": 0},
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        def handle_ws(ws):
            ws.send(
                json.dumps(
                    {
                        "type": "status",
                        "agents_active": [],
                        "tasks_queued": 0,
                        "llm_model": "qwen3.5:9b",
                    }
                )
            )
            ws.send(json.dumps({"type": "study_documents_list", "documents": [pdf_doc, video_doc]}))
            ws.send(
                json.dumps(
                    {
                        "type": "projects_list",
                        "projects": [
                            {"project_id": "dina", "project_name": "Dina", "stack": ["python"]},
                        ],
                    }
                )
            )
            ws.send(json.dumps({"type": "notes_list", "notes": ["Arquitetura.md", "Gestao.md"]}))

            def on_msg(raw):
                try:
                    data = json.loads(raw)
                except Exception:
                    return
                mtype = data.get("type")
                req_id = data.get("request_id")
                if mtype == "list_study_documents":
                    ws.send(json.dumps({"type": "study_documents_list", "documents": [pdf_doc, video_doc], "request_id": req_id}))
                elif mtype == "get_vault_diagnostics":
                    ws.send(
                        json.dumps(
                            {
                                "type": "vault_diagnostics",
                                "diagnostics": {
                                    "total_notes": 2,
                                    "genuine_orphans": 1,
                                    "broken_links": 0,
                                    "notes_requiring_improvement": 1,
                                    "pending_proposals": 0,
                                    "accepted_improvements": 0,
                                    "rejected_suggestions": 0,
                                    "quality_average": 81.5,
                                    "genuine_orphans_list": ["Gestao.md"],
                                    "quality_distribution": {
                                        "ge_80": 1,
                                        "between_70_79": 1,
                                        "between_60_69": 0,
                                        "lt_60": 0,
                                        "total_audited": 2,
                                    },
                                },
                                "queue": [],
                            }
                        )
                    )
                elif mtype == "sentinel_get_status":
                    ws.send(
                        json.dumps(
                            {
                                "type": "sentinel_status",
                                "data": {
                                    "status": "RUNNING",
                                    "posture": "GOOD",
                                    "is_auditing_now": False,
                                    "total_events": 0,
                                    "active_alerts": 0,
                                },
                            }
                        )
                    )
                elif mtype == "study_get_generated_document_status":
                    ws.send(
                        json.dumps(
                            {
                                "type": "study_generated_document_status",
                                "document_id": data.get("document_id"),
                                "status": {"status": "NOT_GENERATED", "versions": []},
                                "request_id": req_id,
                            }
                        )
                    )

            ws.on_message(on_msg)

        page.route_web_socket("ws://127.0.0.1:8001/**", handle_ws)
        page.goto(dist_server, wait_until="domcontentloaded")

        # 1. Standby orb visible, no competing SpatialBoard or unified workspace initially
        assert page.locator('[data-testid="unified-workspace-shell"]').count() == 0
        page.get_by_role("button", name="Estudos").first.click()

        # 2. Unified split-workspace opens with left rail + Study view + promoted Documento IA tab
        shell = page.locator('[data-testid="unified-workspace-shell"]')
        shell.wait_for(state="visible", timeout=5000)
        assert page.locator('[data-testid="rail-domain-study"]').is_visible()
        assert page.locator('#study-nav-generated-doc-btn').is_visible()

        # 3. Document switcher changes PDF -> VIDEO and stays on VIDEO without snapping back
        switcher = page.locator('[data-testid="study-document-switcher"]')
        switcher.wait_for(state="visible", timeout=5000)
        switcher.select_option("doc_vid_test")
        page.locator('[data-testid="study-video-reader-view"]').wait_for(state="visible", timeout=5000)
        page.wait_for_timeout(300)
        assert switcher.input_value() == "doc_vid_test"
        assert page.locator("text=Whisper não instalado").is_visible()
        assert page.locator("text=Techniques & Tools: Plan communications").is_visible()

        # 4. Summary tab renders humanized labels instead of raw snake_case identifiers
        switcher.select_option("doc_pdf_test")
        page.locator('#study-nav-summary-btn').click()
        page.locator("text=síntese interpretativa com IA").wait_for(state="visible", timeout=5000)
        assert page.locator("text=interpretive_synthesis").count() == 0

        # 5. Switch to Phase 5 Documento IA tab directly
        page.locator('#study-nav-generated-doc-btn').click()
        assert page.locator("#study-nav-generated-doc-btn").is_visible()

        # 6. Switch to Code & Projects + Contextual Assistant sidebar
        page.locator('[data-testid="rail-domain-project"]').click()
        assert page.locator("text=JARVIS OS").is_visible()
        page.locator('[data-testid="toggle-context-assistant"]').click()
        page.locator('[data-testid="contextual-jarvis-panel"]').wait_for(state="visible", timeout=5000)

        # 7. Switch to Obsidian Vault & Quality Graph (migrated from SpatialBoard)
        page.locator('[data-testid="rail-domain-obsidian"]').click()
        page.locator('[data-testid="obsidian-vault-view"]').wait_for(state="visible", timeout=5000)
        page.locator('[data-testid="obsidian-vault-view"]').get_by_text("81.5%", exact=True).wait_for(state="visible", timeout=5000)

        # 8. Switch to Sentinel
        page.locator('[data-testid="rail-domain-sentinel"]').click()
        page.locator("text=Postura: GOOD").first.wait_for(state="visible", timeout=5000)

        # 9. Close back to Standby
        page.locator('[data-testid="workspace-close-standby"]').click()
        shell.wait_for(state="detached", timeout=5000)
        assert page_errors == []

        browser.close()
