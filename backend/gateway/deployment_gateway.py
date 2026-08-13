from __future__ import annotations

import httpx
import json
import os
from pathlib import Path
from typing import Any

from sandbox import SANDBOX_DIR, write_project_files, start_local_fallback_server, get_sandbox_status


class WebDeploymentGateway:
    """Deploys MVPs to the local sandbox preview server and performs interactive Playwright DOM verification."""

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
        Performs interactive Playwright DOM inspection (forms, buttons, inputs, console errors).
        Falls back to HTTPX if browser automation is not available.
        """
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                console_errors = []
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

                response = await page.goto(f"{self.base_url}/index.html", wait_until="load", timeout=10000)
                status_code = response.status if response else 0

                title = await page.title()
                forms_count = len(await page.query_selector_all("form"))
                buttons_count = len(await page.query_selector_all("button, input[type='submit']"))
                inputs_count = len(await page.query_selector_all("input, textarea, select"))

                await browser.close()

                is_ok = status_code == 200 and len(console_errors) == 0
                msg = f"Playwright DOM Verificado: Status={status_code}, Form={forms_count}, Buttons={buttons_count}"
                return is_ok, msg, {
                    "method": "PLAYWRIGHT_DOM",
                    "status_code": status_code,
                    "title": title,
                    "forms_count": forms_count,
                    "buttons_count": buttons_count,
                    "inputs_count": inputs_count,
                    "console_errors": console_errors,
                }
        except Exception as e:
            # Fallback to HTTPX GET
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{self.base_url}/index.html")
                    if resp.status_code == 200:
                        return True, "Servidor Sandbox respondeu 200 OK (HTTPX Fallback)", {
                            "method": "HTTPX_FALLBACK",
                            "status_code": 200,
                            "url": f"{self.base_url}/index.html",
                            "content_length": len(resp.text),
                        }
                    return False, f"Servidor respondeu {resp.status_code}", {"status_code": resp.status_code}
            except Exception as http_err:
                return False, f"Falha ao ligar ao sandbox: {str(http_err)}", {"error": str(http_err)}


__all__ = ["WebDeploymentGateway"]
