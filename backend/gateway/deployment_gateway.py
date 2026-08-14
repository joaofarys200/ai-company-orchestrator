from __future__ import annotations

import hashlib
import httpx
import json
import os
import time
from pathlib import Path
from typing import Any

from sandbox import SANDBOX_DIR, write_project_files, start_local_fallback_server, get_sandbox_status


class WebDeploymentGateway:
    """Deploys MVPs to the local sandbox preview server and performs multi-layer interactive Playwright DOM verification."""

    def __init__(self, port: int = 8080):
        self.port = port
        self.base_url = f"http://127.0.0.1:{self.port}"

    def deploy_local_mvp(self, html: str, css: str = "", js: str = "") -> dict[str, Any]:
        """Writes project files to sandbox_dir and ensures local HTTP fallback server is running."""
        write_project_files(html, css, js)
        start_local_fallback_server()
        return {
            "status": "DEPLOYED",
            "url": self.base_url,
            "preview_path": f"{self.base_url}/index.html",
            "health_path": f"{self.base_url}/healthz",
        }

    async def verify_deployment_health(self) -> tuple[bool, str, dict[str, Any]]:
        """
        Performs multi-layer verification:
        1. Valid HTTP 200 response
        2. HTML content loaded and non-empty
        3. DOM contains functional interactive elements (forms, buttons, inputs)
        4. Absence of unhandled JavaScript page errors (pageerror)
        5. Absence of critical console errors
        6. Screenshot evidence captured with SHA-256 fingerprint
        """
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                console_errors: list[str] = []
                page_errors: list[str] = []

                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda err: page_errors.append(str(err)))

                response = await page.goto(f"{self.base_url}/index.html", wait_until="load", timeout=10000)
                status_code = response.status if response else 0

                title = await page.title()
                forms_count = len(await page.query_selector_all("form"))
                buttons_count = len(await page.query_selector_all("button, input[type='submit']"))
                inputs_count = len(await page.query_selector_all("input, textarea, select"))
                headings_count = len(await page.query_selector_all("h1, h2, h3, h4"))
                body_text = await page.inner_text("body") if await page.query_selector("body") else ""
                body_text_len = len(body_text.strip())

                # Capture visual proof
                screenshots_dir = Path("workspace/.jarvis/screenshots")
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                shot_path = screenshots_dir / f"deploy_{int(time.time() * 1000)}.png"
                await page.screenshot(path=str(shot_path))
                
                with open(shot_path, "rb") as f:
                    shot_sha256 = hashlib.sha256(f.read()).hexdigest()

                await browser.close()

                # Multi-layer truth evaluation
                has_elements = (forms_count > 0 or buttons_count > 0 or inputs_count > 0 or headings_count > 0)
                has_content = body_text_len > 15
                no_js_crashes = (len(page_errors) == 0 and len(console_errors) == 0)
                http_valid = (status_code == 200)

                is_ok = http_valid and has_elements and has_content and no_js_crashes

                if not is_ok:
                    reasons = []
                    if not http_valid:
                        reasons.append(f"HTTP Status={status_code}")
                    if not has_content:
                        reasons.append("DOM vazio/sem conteúdo visível")
                    if not has_elements:
                        reasons.append("Nenhum elemento interativo ou estrutural encontrado")
                    if len(page_errors) > 0:
                        reasons.append(f"Erro fatal de JS na página: {page_errors[0]}")
                    if len(console_errors) > 0:
                        reasons.append(f"Erros de consola: {console_errors[0]}")
                    msg = f"Falha na validação de deploy: {', '.join(reasons)}"
                else:
                    msg = f"Playwright DOM Verificado: Status={status_code}, Form={forms_count}, Buttons={buttons_count}, Inputs={inputs_count}"

                return is_ok, msg, {
                    "method": "PLAYWRIGHT_DOM_MULTILAYER",
                    "status_code": status_code,
                    "title": title,
                    "forms_count": forms_count,
                    "buttons_count": buttons_count,
                    "inputs_count": inputs_count,
                    "headings_count": headings_count,
                    "body_text_length": body_text_len,
                    "page_errors": page_errors,
                    "console_errors": console_errors,
                    "screenshot_path": str(shot_path),
                    "screenshot_sha256": shot_sha256,
                }
        except Exception as e:
            # Fallback to HTTPX GET with strict content inspection
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{self.base_url}/index.html")
                    text = resp.text.strip()
                    has_html_content = len(text) > 50 and ("<body" in text.lower() or "<div" in text.lower() or "<form" in text.lower())
                    if resp.status_code == 200 and has_html_content:
                        return True, "Servidor Sandbox respondeu 200 OK com conteúdo HTML válido (HTTPX Fallback)", {
                            "method": "HTTPX_FALLBACK",
                            "status_code": 200,
                            "url": f"{self.base_url}/index.html",
                            "content_length": len(resp.text),
                        }
                    elif resp.status_code == 200 and not has_html_content:
                        return False, "Sandbox devolveu 200 OK mas HTML está vazio ou sem estrutura (HTTPX Fallback)", {
                            "method": "HTTPX_FALLBACK",
                            "status_code": 200,
                            "content_length": len(resp.text),
                        }
                    return False, f"Servidor respondeu {resp.status_code}", {"status_code": resp.status_code}
            except Exception as http_err:
                return False, f"Falha ao ligar ao sandbox: {str(http_err)}", {"error": str(http_err)}


__all__ = ["WebDeploymentGateway"]
