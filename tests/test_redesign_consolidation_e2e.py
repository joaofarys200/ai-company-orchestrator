import base64
import functools
import http.server
import json
import os
import socketserver
import threading
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
import pytest


DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
SCREENSHOT_DIR = Path(
    os.environ.get(
        "JARVIS_SCREENSHOT_DIR",
        r"C:\Users\joaor\.gemini\antigravity\brain\7671961e-b812-4384-9eac-bbe685b273d1\scratch\screenshots",
    )
)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def _make_sample_pdf_base64() -> str:
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>endobj\n"
        b"4 0 obj<< /Length 44 >>stream\nBT /F1 18 Tf 72 700 Td (Gestao de Projetos EVM) Tj ET\nendstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000202 00000 n \n"
        b"trailer<< /Size 5 /Root 1 0 R >>\nstartxref\n295\n%%EOF"
    )
    return base64.b64encode(pdf_bytes).decode("ascii")


@pytest.fixture(scope="module")
def dist_http_server():
    if not DIST_DIR.exists():
        pytest.skip("frontend/dist missing - run npm run build first")
    handler = functools.partial(_QuietHandler, directory=str(DIST_DIR))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_full_redesign_consolidation_and_screenshots(dist_http_server):
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    sample_pdf_b64 = _make_sample_pdf_base64()
    ws_requests = []
    page_errors = []

    project_files = {
        "src/main.py": "def run():\n    return 'Jarvis IDE ready'\n\nif __name__ == '__main__':\n    print(run())\n",
        "README.md": "# Jarvis Demo Project\n\nIntegrated IDE workspace.\n",
    }

    study_docs = [
        {
            "document_id": "doc_pdf_test",
            "title": "Gestao de Projetos e Earned Value (EVM)",
            "subject": "Gestao de Projetos",
            "source_type": "PDF",
            "language": "pt",
            "page_count": 12,
            "created_at": "2026-11-10T10:00:00",
            "updated_at": "2026-11-12T10:00:00",
            "reading_progress": {"current_page": 3, "current_section": "Metricas EVM", "progress_percent": 38, "last_read_at": "2026-11-12T10:00:00"},
            "sections": [
                {"section_id": "sec_1", "title": "Introducao EVM", "page_start": 1, "page_end": 2, "content": "Earned Value Management integra ambito, prazo e custo."},
                {"section_id": "sec_2", "title": "Metricas Base PV, EV, AC", "page_start": 3, "page_end": 5, "content": "CPI = EV / AC e SPI = EV / PV."},
            ],
            "pages": [
                {"page_number": 1, "text": "Introducao ao Earned Value Management"},
                {"page_number": 3, "text": "Metricas CPI, SPI e Curva S"},
            ],
            "metadata": {
                "generation_telemetry": {"mode": "grounded_llm", "model": "qwen3.5:9b"},
                "generated_study_document": {
                    "version": 1,
                    "title": "Guia Completo de Earned Value Management",
                    "status": "completed",
                    "pdf_path": "generated/evm_v1.pdf",
                },
            },
        },
        {
            "document_id": "doc_vid_test",
            "title": "000 Planning Part Iii (Communication)",
            "subject": "Gestao de Projetos",
            "source_type": "VIDEO",
            "language": "en",
            "page_count": 0,
            "created_at": "2026-11-11T09:00:00",
            "updated_at": "2026-11-11T09:00:00",
            "reading_progress": {"current_page": 1, "progress_percent": 52, "last_read_at": "2026-11-11T15:00:00"},
            "metadata": {
                "video": {
                    "duration_seconds": 360,
                    "whisper_status": "not_installed",
                    "whisper_message": "Whisper não instalado — transcrição extraída dos diapositivos por OCR.",
                    "transcript_segments": [
                        {"start": 5, "end": 35, "text": "Techniques & Tools: Plan communications and stakeholder matrix."}
                    ],
                    "chapters": [
                        {"chapter_id": "ch1", "title": "Stakeholder Matrix", "start_time": 0, "end_time": 180}
                    ],
                    "keyframes": [
                        {"frame_id": "kf_1", "timestamp": 12, "timestamp_str": "00:12", "ocr_text": "Techniques & Tools: Plan communications", "image_path": "frames/kf_1.png"}
                    ],
                }
            },
        },
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1360, "height": 850})
        page = context.new_page()
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        def handle_ws(ws):
            def send(payload):
                ws.send(json.dumps(payload))

            def on_msg(raw):
                msg = json.loads(raw)
                mtype = msg.get("type")
                req_id = msg.get("request_id")
                ws_requests.append(msg)
                if mtype == "list_projects":
                    send(
                        {
                            "type": "projects_list",
                            "projects": [
                                {"project_id": "jarvis-demo", "project_name": "JARVIS Demo App", "root_path": "C:/workspaces/jarvis-demo"},
                                {"project_id": "ml-pipeline", "project_name": "ML Pipeline Core", "root_path": "C:/workspaces/ml-pipeline"},
                            ],
                        }
                    )
                elif mtype == "open_project":
                    pid = msg.get("project_id") or "jarvis-demo"
                    send(
                        {
                            "type": "project_context",
                            "context": {
                                "project_id": pid,
                                "project_name": "JARVIS Demo App" if pid == "jarvis-demo" else pid,
                                "root_path": f"C:/workspaces/{pid}",
                                "total_files": len(project_files),
                                "languages": ["Python", "Markdown"],
                                "entrypoints": ["src/main.py"],
                                "suggested_commands": [{"kind": "test", "command": "pytest -q", "source": "pytest.ini"}],
                            },
                            "files": dict(project_files),
                            "file_hashes": {},
                            "symbols": {},
                        }
                    )
                elif mtype == "create_project_file":
                    fname = msg.get("filename")
                    content = msg.get("content", "")
                    project_files[fname] = content
                    send({"type": "file", "filename": fname, "content": content})
                    send({"type": "project_file_save_result", "ok": True, "filename": fname, "sha256": "abc123"})
                elif mtype == "rename_project_file":
                    old_f = msg.get("old_filename")
                    new_f = msg.get("new_filename")
                    content = project_files.pop(old_f, "")
                    project_files[new_f] = content
                    send({"type": "project_file_deleted", "project_id": msg.get("project_id"), "filename": old_f, "success": True})
                    send({"type": "file", "filename": new_f, "content": content})
                elif mtype == "list_study_documents":
                    send({"type": "study_documents_list", "documents": study_docs, "collections": [], "request_id": req_id})
                elif mtype == "study_get_document_details":
                    doc_id = msg.get("document_id")
                    doc = next((d for d in study_docs if d["document_id"] == doc_id), study_docs[0])
                    send(
                        {
                            "type": "study_document_details",
                            "document": doc,
                            "reading_notes": [
                                {"note_id": "rn1", "document_id": doc_id, "page": 3, "selection": "CPI = EV / AC", "note": "Racio de eficiencia de custo", "created_at": "2026-11-12 10:15:00"}
                            ],
                            "highlights": [],
                            "request_id": req_id,
                        }
                    )
                elif mtype == "study_get_document_file":
                    send({"type": "study_document_file_result", "document_id": msg.get("document_id"), "filename": "evm.pdf", "content_base64": sample_pdf_b64, "request_id": req_id})
                elif mtype == "study_get_generated_document_status":
                    send(
                        {
                            "type": "study_generated_document_status_result",
                            "document_id": msg.get("document_id"),
                            "status": {
                                "state": "COMPLETED",
                                "version": 1,
                                "has_pdf": True,
                                "has_docx": True,
                                "pdf_path": "generated/evm_v1.pdf",
                                "docx_path": "generated/evm_v1.docx",
                            },
                            "request_id": req_id,
                        }
                    )
                elif mtype == "study_get_generated_document_file":
                    send(
                        {
                            "type": "study_generated_document_file_result",
                            "document_id": msg.get("document_id"),
                            "format": msg.get("format", "pdf"),
                            "filename": "evm_study_doc.pdf",
                            "mime_type": "application/pdf",
                            "base64_data": sample_pdf_b64,
                            "request_id": req_id,
                        }
                    )
                elif mtype == "get_rules":
                    send(
                        {
                            "type": "rules_list",
                            "rules": [{"rule_key": "no_mock_metrics", "description": "Nunca inventar metricas sinteticas.", "correction": "Usar valores reais do backend."}],
                        }
                    )
                    send(
                        {
                            "type": "architecture_list",
                            "architecture": [{"module": "StudyService", "purpose": "Orquestra pipeline academico local", "constraints": "Ollama qwen3.5:9b apenas"}],
                        }
                    )
                    send(
                        {
                            "type": "decisions_list",
                            "decisions": [{"decision": "Shell unificado Dark Navy", "reason": "Eliminar UI duplicada SpatialBoard/WorkspaceViewer", "impact": "Workspace unico"}],
                        }
                    )
                elif mtype == "list_notes":
                    send({"type": "notes_list", "notes": ["EVM_Resumo.md", "Arquitetura_StudyEngine.md", "Nota_Orfa_Teste.md"]})
                elif mtype == "read_note":
                    send({"type": "note_content", "filename": msg.get("filename"), "content": "# Nota Obsidian\n\nLigada a [[Arquitetura_StudyEngine]].\n", "request_id": req_id})
                elif mtype == "get_vault_diagnostics":
                    send(
                        {
                            "type": "vault_diagnostics",
                            "request_id": req_id,
                            "queue": [],
                            "diagnostics": {
                                "quality_average": 84.2,
                                "total_notes": 3,
                                "genuine_orphans": 1,
                                "genuine_orphans_list": ["Nota_Orfa_Teste.md"],
                                "broken_links": 0,
                                "notes_requiring_improvement": 1,
                                "graph_nodes": [
                                    {"id": "EVM_Resumo.md", "label": "EVM_Resumo", "in_degree": 1, "out_degree": 1, "degree": 2, "score": 90.0, "is_hub": True, "is_orphan": False},
                                    {"id": "Arquitetura_StudyEngine.md", "label": "Arquitetura_StudyEngine", "in_degree": 1, "out_degree": 1, "degree": 2, "score": 88.0, "is_hub": True, "is_orphan": False},
                                    {"id": "Nota_Orfa_Teste.md", "label": "Nota_Orfa_Teste", "in_degree": 0, "out_degree": 0, "degree": 0, "score": 52.0, "is_hub": False, "is_orphan": True},
                                ],
                                "graph_edges": [{"source": "EVM_Resumo.md", "target": "Arquitetura_StudyEngine.md"}],
                            },
                        }
                    )
                elif mtype in ("sentinel_get_status", "sentinel_run_audit"):
                    send({"type": "sentinel_status", "data": {"posture": "GOOD", "status": "RUNNING", "is_auditing_now": False, "shadow_mode": True, "total_events": 0, "active_alerts": 0}})
                elif mtype == "sentinel_get_baseline":
                    send({"type": "sentinel_baseline", "data": {"processes": [{"name": "python.exe", "pid": 4120}], "network": [], "persistence": [], "browser_extensions": []}})
                elif mtype == "sentinel_get_actions":
                    send({"type": "sentinel_actions_list", "data": [{"action_id": "act-1", "title": "Rever ligacao suspeita", "status": "WAITING_APPROVAL", "severity": "HIGH"}]})

            ws.on_message(on_msg)
            send(
                {
                    "type": "status",
                    "status": "online",
                    "projects": [{"project_id": "jarvis-demo", "project_name": "JARVIS Demo App", "root_path": "C:/workspaces/jarvis-demo"}],
                    "sentinel": {"posture": "GOOD", "shadow_mode": True},
                }
            )
            send({"type": "study_documents_list", "documents": study_docs, "collections": []})
            send(
                {
                    "type": "projects_list",
                    "projects": [
                        {"project_id": "jarvis-demo", "project_name": "JARVIS Demo App", "root_path": "C:/workspaces/jarvis-demo"},
                        {"project_id": "ml-pipeline", "project_name": "ML Pipeline Core", "root_path": "C:/workspaces/ml-pipeline"},
                    ],
                }
            )
            send({"type": "notes_list", "notes": ["EVM_Resumo.md", "Arquitetura_StudyEngine.md", "Nota_Orfa_Teste.md"]})

        page.route_web_socket("ws://127.0.0.1:8001/**", handle_ws)
        page.goto(f"{dist_http_server}/index.html")
        page.wait_for_timeout(400)

        # 1. Standby -> Open Estudos
        page.screenshot(path=str(SCREENSHOT_DIR / "01_standby_home.png"))
        page.get_by_role("button", name="Estudos").first.click()
        page.wait_for_selector('[data-testid="unified-workspace-shell"]')
        page.wait_for_timeout(300)
        page.screenshot(path=str(SCREENSHOT_DIR / "02_study_pdf_reader.png"))

        # 2. Study Overview / Landing
        page.locator("#study-nav-overview-btn").click()
        page.wait_for_selector('[data-testid="study-landing-view"]')
        page.screenshot(path=str(SCREENSHOT_DIR / "03_study_landing.png"))

        # 3. Study Library List + Grid toggle
        page.locator("#study-nav-library-btn").click()
        page.wait_for_selector('[data-testid="study-library-view"]')
        page.screenshot(path=str(SCREENSHOT_DIR / "04_study_library_list.png"))
        page.locator('[data-testid="study-library-view-grid"]').click()
        page.wait_for_timeout(150)

        # 4. Switch to Video Doc & verify Video Reader + Practice Dropdown -> Lectures
        page.locator('[data-testid="study-document-switcher"]').select_option("doc_vid_test")
        page.wait_for_selector('[data-testid="study-video-reader-view"]')
        page.wait_for_timeout(200)
        page.screenshot(path=str(SCREENSHOT_DIR / "05_study_video_reader.png"))

        page.locator('[data-testid="study-nav-practice-btn"]').click()
        page.wait_for_selector('[data-testid="study-practice-dropdown"]')
        page.locator("#study-nav-lectures-btn").click()
        page.wait_for_timeout(200)

        # 5. Switch back to PDF & verify Generated Doc inline preview
        page.locator('[data-testid="study-document-switcher"]').select_option("doc_pdf_test")
        page.locator("#study-nav-generated-doc-btn").click()
        page.wait_for_selector('[data-testid="generated-doc-preview-toggle"]')
        page.locator('[data-testid="generated-doc-preview-toggle"]').click()
        page.wait_for_selector('[data-testid="generated-doc-inline-preview"]')
        page.wait_for_timeout(200)
        page.screenshot(path=str(SCREENSHOT_DIR / "06_study_generated_doc_preview.png"))

        # 6. Projects Landing & IDE Editor + Create/Rename + Bottom Dock + Spatial Overview
        page.locator('[data-testid="rail-domain-project"]').click()
        page.wait_for_selector('[data-testid="projects-landing-view"]')
        page.screenshot(path=str(SCREENSHOT_DIR / "07_projects_landing.png"))

        page.get_by_text("JARVIS Demo App").first.click()
        page.locator('[data-testid="ide-dock-tab-console"]').click()
        page.wait_for_selector('[data-testid="ide-bottom-dock"]')
        page.locator('[data-testid="ide-new-file-btn"]').click()
        page.locator('[data-testid="ide-new-file-input"]').fill("src/helper.py")
        page.locator('[data-testid="ide-new-file-input"]').press("Enter")
        page.wait_for_timeout(200)
        assert any(m.get("type") == "create_project_file" for m in ws_requests)
        page.screenshot(path=str(SCREENSHOT_DIR / "08_project_ide_dock.png"))

        # Toggle Spatial Overview Overlay
        page.locator('[data-testid="toggle-spatial-overview"]').click()
        page.wait_for_selector('[data-testid="spatial-overview-panel"]')
        page.screenshot(path=str(SCREENSHOT_DIR / "09_spatial_overview_overlay.png"))
        page.locator('[data-testid="toggle-spatial-overview"]').click()

        # 7. Obsidian Vault + Graph + Rules
        page.locator('[data-testid="rail-domain-obsidian"]').click()
        page.wait_for_selector('[data-testid="obsidian-vault-view"]')
        page.locator('[data-testid="obsidian-tab-graph"]').click()
        page.wait_for_selector('[data-testid="obsidian-graph-canvas"]')
        page.screenshot(path=str(SCREENSHOT_DIR / "10_obsidian_graph.png"))
        page.locator('[data-testid="obsidian-tab-rules"]').click()
        page.wait_for_selector('[data-testid="obsidian-rules-panel"]')

        # 8. Sentinel + Global Chat Drawer + Assistant Panel
        page.locator('[data-testid="rail-domain-sentinel"]').click()
        page.wait_for_selector('[data-testid="sentinel-severity-strip"]')
        assert page.get_by_text("Postura: GOOD").first.is_visible()
        page.screenshot(path=str(SCREENSHOT_DIR / "11_sentinel_cockpit.png"))

        page.locator('[data-testid="open-global-chat-btn"]').click()
        page.wait_for_timeout(350)
        page.screenshot(path=str(SCREENSHOT_DIR / "12_global_chat_drawer.png"))

        assert page_errors == [], f"Uncaught frontend page errors: {page_errors}"
        browser.close()

