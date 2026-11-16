"""
JARVIS OS — Real Browser QA Integration Validator
Invoca e orquestra a execução de testes no navegador real (Microsoft Edge / Playwright)
e reconcilia com a governança de aceitação de produto.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from backend.process_utils import hidden_subprocess_kwargs

logger = logging.getLogger("Jarvis.RealBrowserQA")


class RealBrowserQAValidator:
    """Valida o preview real através de testes de browser de ponta a ponta."""

    RUNNER_SCRIPT = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "scripts",
        "run_real_browser_qa.cjs",
    )

    ARTIFACTS_DIR = "C:/Users/joaor/.gemini/antigravity-ide/brain/b312d351-2732-4aea-a0a9-e218fa8e1fba"

    @classmethod
    def _parse_runner_json(cls, *streams: str) -> Optional[Dict[str, Any]]:
        for stream in streams:
            for line in reversed(stream.strip().splitlines()):
                candidate = line.strip()
                if candidate.startswith("{") and candidate.endswith("}"):
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict):
                            return parsed
                    except Exception:
                        continue
        return None

    @classmethod
    def _execute_python_playwright_qa(
        cls,
        preview_url: str,
        mission_id: str,
        evidence_dir: str,
        timeout_seconds: float,
    ) -> Optional[Dict[str, Any]]:
        """Executa o mesmo protocolo de Browser QA via Playwright Python (Edge/Chromium)."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None

        os.makedirs(evidence_dir, exist_ok=True)
        result: Dict[str, Any] = {
            "available": True,
            "valid": False,
            "target_url": preview_url,
            "mission_id": mission_id,
            "page_loaded": False,
            "title": "",
            "console_errors": [],
            "page_errors": [],
            "network_failures": [],
            "is_blank_page": False,
            "is_inert_button": False,
            "interaction_performed": False,
            "interaction_result_valid": False,
            "cards_found": 0,
            "has_rich_device_cards": False,
            "has_legacy_raw_ips_only": False,
            "sample_rendered_text": "",
            "evidence_screenshots": [],
            "screenshots": [],
            "violations": [],
        }

        browser = None
        try:
            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch(headless=True, channel="msedge")
                except Exception:
                    browser = p.chromium.launch(headless=True)

                context = browser.new_context(viewport={"width": 1440, "height": 900})
                page = context.new_page()

                def _on_console(msg: Any) -> None:
                    if getattr(msg, "type", "") == "error":
                        text = str(getattr(msg, "text", ""))
                        if "favicon.ico" not in text:
                            result["console_errors"].append(text)

                def _on_request_failed(req: Any) -> None:
                    failure = getattr(req, "failure", None)
                    err_txt = failure.get("errorText") if isinstance(failure, dict) else str(failure or "Failed")
                    result["network_failures"].append({"url": getattr(req, "url", ""), "errorText": err_txt})

                page.on("console", _on_console)
                page.on("pageerror", lambda err: result["page_errors"].append(str(err)))
                page.on("requestfailed", _on_request_failed)

                goto_timeout_ms = int(min(max(timeout_seconds, 5.0), 25.0) * 1000)
                page.goto(preview_url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
                result["page_loaded"] = True
                result["title"] = page.title()

                body_text = (page.evaluate("() => document.body ? document.body.innerText.trim() : ''") or "").strip()
                if len(body_text) < 30:
                    result["is_blank_page"] = True
                    result["violations"].append(
                        "BLANK_PAGE_ERROR: O documento carregou mas o corpo está em branco ou sem conteúdo."
                    )

                ss_before = os.path.join(evidence_dir, f"{mission_id}_01_before_interaction.png")
                page.screenshot(path=ss_before, full_page=True)
                result["evidence_screenshots"].append(ss_before)

                scan_btn = page.query_selector("#scanIpButton")
                generic_btn = None if scan_btn else page.query_selector("#refreshMetricsBtn, #fetchAuditBtn, button")

                if scan_btn:
                    result["interaction_performed"] = True
                    initial_html = page.evaluate(
                        "() => { const el = document.getElementById('ipScanResults'); return el ? el.innerHTML : ''; }"
                    ) or ""
                    scan_btn.click()
                    try:
                        page.wait_for_function(
                            """() => {
                                const res = document.getElementById('ipScanResults');
                                const spinner = document.getElementById('ipScanLoadingSpinner');
                                const spinnerHidden = !spinner || spinner.style.display === 'none';
                                const hasContent = res && res.children.length > 0 && !res.innerText.includes('Consultando');
                                return spinnerHidden && hasContent;
                            }""",
                            timeout=8000,
                        )
                    except Exception:
                        pass

                    post_html = page.evaluate(
                        "() => { const el = document.getElementById('ipScanResults'); return el ? el.innerHTML : ''; }"
                    ) or ""
                    post_text = (
                        page.evaluate(
                            "() => { const el = document.getElementById('ipScanResults'); return el ? el.innerText.trim() : ''; }"
                        )
                        or ""
                    )
                    result["sample_rendered_text"] = post_text[:300]

                    if initial_html == post_html and not post_text:
                        result["is_inert_button"] = True
                        result["violations"].append(
                            "INERT_CONTROL_ERROR: O botão de interação foi clicado mas não desencadeou qualquer alteração no DOM."
                        )

                    card_count = int(
                        page.evaluate(
                            "() => { const el = document.getElementById('ipScanResults'); return el ? el.querySelectorAll('li').length : 0; }"
                        )
                        or 0
                    )
                    result["cards_found"] = card_count
                    if "Fabricante:" in post_html or "MAC:" in post_html:
                        result["has_rich_device_cards"] = True
                        result["interaction_result_valid"] = True
                    elif "🌐" in post_html and card_count > 0:
                        result["has_legacy_raw_ips_only"] = True
                        result["violations"].append(
                            "SILENT_FALLBACK_REGRESSION: O frontend renderizou apenas a lista crua legada de IPs (🌐), sem cartões de Fabricante/MAC/Hostname."
                        )
                    elif card_count == 0 and "Nenhum dispositivo" not in post_text:
                        result["violations"].append(
                            "RENDER_FAILURE: Nenhum dispositivo ou mensagem de conclusão foi renderizada em #ipScanResults."
                        )
                    else:
                        result["interaction_result_valid"] = True

                    ss_after = os.path.join(evidence_dir, f"{mission_id}_02_after_interaction.png")
                    page.screenshot(path=ss_after, full_page=True)
                    result["evidence_screenshots"].append(ss_after)
                elif generic_btn:
                    result["interaction_performed"] = True
                    initial_html = page.evaluate("() => document.body.innerHTML") or ""
                    generic_btn.click()
                    page.wait_for_timeout(1000)
                    post_html = page.evaluate("() => document.body.innerHTML") or ""
                    if initial_html == post_html:
                        result["is_inert_button"] = True
                        result["violations"].append("INERT_CONTROL_ERROR: O botão clicado não alterou o DOM.")
                    else:
                        result["interaction_result_valid"] = True
                    ss_after = os.path.join(evidence_dir, f"{mission_id}_02_after_interaction.png")
                    page.screenshot(path=ss_after, full_page=True)
                    result["evidence_screenshots"].append(ss_after)
                else:
                    result["interaction_result_valid"] = True

                for ce in result["console_errors"]:
                    result["violations"].append(f"BROWSER_CONSOLE_ERROR: {ce}")
                for pe in result["page_errors"]:
                    result["violations"].append(f"UNCAUGHT_PAGE_EXCEPTION: {pe}")

                result["screenshots"] = list(result["evidence_screenshots"])
                cls._copy_evidence_to_artifacts(result["screenshots"])
                result["valid"] = (
                    result["page_loaded"]
                    and not result["is_blank_page"]
                    and not result["is_inert_button"]
                    and not result["has_legacy_raw_ips_only"]
                    and result["interaction_result_valid"]
                    and len(result["violations"]) == 0
                )
        except Exception as exc:
            result["violations"].append(f"BROWSER_QA_FATAL_ERROR: {exc}")
            result["valid"] = False
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
        return result

    @classmethod
    def execute_browser_qa(
        cls,
        preview_url: str,
        mission_id: str = "qa_mission",
        evidence_dir: Optional[str] = None,
        timeout_seconds: float = 25.0,
        actions: Optional[List[Dict[str, Any]]] = None,
        project_id: str = "",
        timeout_ms: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Executa o runner Node/Edge QA e recorre a Playwright Python em ambiente de dev/testes se disponível."""
        if timeout_ms:
            timeout_seconds = timeout_ms / 1000.0

        resolved_evidence_dir = evidence_dir or os.path.join(
            tempfile.gettempdir(),
            "jarvis_browser_qa_evidence",
        )
        os.makedirs(resolved_evidence_dir, exist_ok=True)

        node_bin = shutil.which("node")
        if os.path.isfile(cls.RUNNER_SCRIPT) and node_bin:
            cmd = [
                node_bin,
                cls.RUNNER_SCRIPT,
                preview_url,
                mission_id,
                resolved_evidence_dir,
            ]
            try:
                res = subprocess.run(
                    cmd,
                    **hidden_subprocess_kwargs(
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds,
                    ),
                )
                data = cls._parse_runner_json(res.stdout, res.stderr)
                if data is not None:
                    if data.get("available"):
                        screenshots = data.get("evidence_screenshots", [])
                        data["screenshots"] = screenshots
                        cls._copy_evidence_to_artifacts(screenshots)
                        return data
                    # Node runner present, but npm `playwright` is not installed (kept dev-only in Python venv).
                    py_res = cls._execute_python_playwright_qa(
                        preview_url,
                        mission_id,
                        resolved_evidence_dir,
                        timeout_seconds,
                    )
                    if py_res is not None:
                        return py_res
                    return data

                return {
                    "available": True,
                    "valid": False,
                    "status": "FAIL",
                    "violations": [
                        f"Saída inesperada do Browser QA runner: {res.stdout.strip()[:200]} {res.stderr.strip()[:200]}"
                    ],
                    "evidence_screenshots": [],
                }
            except subprocess.TimeoutExpired:
                return {
                    "available": True,
                    "valid": False,
                    "status": "FAIL",
                    "violations": [f"Browser QA excedeu o tempo limite de {timeout_seconds}s contra {preview_url}."],
                    "evidence_screenshots": [],
                }
            except Exception as exc:
                py_res = cls._execute_python_playwright_qa(
                    preview_url,
                    mission_id,
                    resolved_evidence_dir,
                    timeout_seconds,
                )
                if py_res is not None:
                    return py_res
                return {
                    "available": False,
                    "valid": False,
                    "status": "INSUFFICIENT_EVIDENCE",
                    "violations": [f"Erro ao executar runner do browser: {exc}"],
                    "evidence_screenshots": [],
                }

        py_res = cls._execute_python_playwright_qa(
            preview_url,
            mission_id,
            resolved_evidence_dir,
            timeout_seconds,
        )
        if py_res is not None:
            return py_res

        missing_reason = (
            f"Runner script ausente: {cls.RUNNER_SCRIPT}"
            if not os.path.isfile(cls.RUNNER_SCRIPT)
            else "Node.js / Playwright indisponíveis neste ambiente"
        )
        return {
            "available": False,
            "valid": False,
            "status": "INSUFFICIENT_EVIDENCE",
            "violations": [missing_reason],
            "screenshots": [],
            "evidence_screenshots": [],
        }

    @classmethod
    def _copy_evidence_to_artifacts(cls, screenshots: List[str]) -> None:
        if not os.path.isdir(cls.ARTIFACTS_DIR):
            return
        for s in screenshots:
            if os.path.isfile(s):
                try:
                    dest = os.path.join(cls.ARTIFACTS_DIR, os.path.basename(s))
                    shutil.copy2(s, dest)
                except Exception:
                    pass
