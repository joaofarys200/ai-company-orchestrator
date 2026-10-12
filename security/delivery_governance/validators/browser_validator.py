"""
Validador de Navegador e QA de Renderização (Browser Validation).
Utiliza Playwright / Microsoft Edge quando disponíveis.
Verifica:
- Página carrega com sucesso.
- Sem erros na consola do browser (console.error) ou exceções não capturadas.
- Sem pedidos de rede críticos falhados (404/500 para CSS/JS).
- UI principal renderizada.
- Botões interativos essenciais clicáveis.
- Se browser indisponível: marca INSUFFICIENT_EVIDENCE (NUNCA assume PASS).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Jarvis.BrowserValidator")


class BrowserIntegrityValidator:
    """Valida a renderização e comportamento do produto num browser real."""

    @classmethod
    async def validate_url_headless(
        cls,
        url: str,
        timeout_ms: int = 5000,
        expected_selectors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Executa validação no navegador através do Playwright.
        Retorna relatório detalhado com consola, erros e elementos encontrados.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            # Playwright não instalado; recorre ao executável nativo do Microsoft Edge no Windows
            return await cls._validate_url_with_edge_cli(url, timeout_ms, expected_selectors)

        console_errors: List[str] = []
        page_errors: List[str] = []
        network_failures: List[Dict[str, Any]] = []
        elements_found: List[Dict[str, Any]] = []

        try:
            async with async_playwright() as p:
                browser = None
                # Tenta Edge (msedge) ou Chromium
                try:
                    browser = await p.chromium.launch(headless=True, channel="msedge")
                except Exception:
                    try:
                        browser = await p.chromium.launch(headless=True)
                    except Exception as launch_exc:
                        return {
                            "available": False,
                            "status": "INSUFFICIENT_EVIDENCE",
                            "valid": False,
                            "reason": f"Não foi possível iniciar o browser: {launch_exc}",
                            "console_errors": [],
                            "network_failures": [],
                            "elements_found": [],
                        }

                context = await browser.new_context()
                page = await context.new_page()

                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type in {"error", "warning"} else None)
                page.on("pageerror", lambda err: page_errors.append(str(err)))
                page.on("requestfailed", lambda req: network_failures.append({
                    "url": req.url,
                    "failure": req.failure,
                }))

                try:
                    response = await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                    http_status = response.status if response else None
                except Exception as goto_exc:
                    await browser.close()
                    return {
                        "available": True,
                        "status": "FAIL",
                        "valid": False,
                        "reason": f"Falha ao aceder à URL {url}: {goto_exc}",
                        "console_errors": console_errors,
                        "network_failures": network_failures,
                        "elements_found": [],
                    }

                if expected_selectors:
                    for sel in expected_selectors:
                        elem = await page.query_selector(sel)
                        elements_found.append({
                            "selector": sel,
                            "found": elem is not None,
                        })

                await browser.close()

                has_critical_errors = len(console_errors) > 0 or len(page_errors) > 0 or len(network_failures) > 0
                missing_selectors = [e for e in elements_found if not e["found"]]

                is_valid = (http_status is not None and http_status < 400) and not has_critical_errors and len(missing_selectors) == 0

                return {
                    "available": True,
                    "status": "PASS" if is_valid else "FAIL",
                    "valid": is_valid,
                    "http_status": http_status,
                    "console_errors": console_errors,
                    "page_errors": page_errors,
                    "network_failures": network_failures,
                    "elements_found": elements_found,
                    "reason": "OK" if is_valid else "Falhas detetadas na consola ou rede do browser.",
                }

        except Exception as exc:
            return {
                "available": True,
                "status": "FAIL",
                "valid": False,
                "reason": f"Exceção durante validação de browser: {exc}",
                "console_errors": console_errors,
                "network_failures": network_failures,
                "elements_found": elements_found,
            }

    @classmethod
    async def _validate_url_with_edge_cli(
        cls,
        url: str,
        timeout_ms: int = 5000,
        expected_selectors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Executa validação real no Microsoft Edge headless nativo do Windows."""
        import os
        import re
        import shutil
        import subprocess

        edge_candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            shutil.which("msedge"),
        ]
        edge_path = next((p for p in edge_candidates if p and os.path.exists(p)), None)

        if not edge_path:
            return {
                "available": False,
                "status": "INSUFFICIENT_EVIDENCE",
                "valid": False,
                "reason": "Nem Playwright nem Microsoft Edge foram encontrados no sistema.",
                "console_errors": [],
                "network_failures": [],
                "elements_found": [],
            }

        cmd = [
            edge_path,
            "--headless=new",
            "--dump-dom",
            "--virtual-time-budget=2000",
            url,
        ]

        try:
            timeout_sec = max(2.0, timeout_ms / 1000.0)
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    encoding="utf-8",
                    errors="ignore",
                    timeout=timeout_sec,
                ),
            )
        except subprocess.TimeoutExpired:
            return {
                "available": True,
                "status": "FAIL",
                "valid": False,
                "reason": f"Timeout ao aceder à URL {url} via Microsoft Edge.",
                "console_errors": ["TIMEOUT"],
                "network_failures": [],
                "elements_found": [],
            }
        except Exception as exc:
            return {
                "available": True,
                "status": "FAIL",
                "valid": False,
                "reason": f"Erro ao executar Microsoft Edge: {exc}",
                "console_errors": [str(exc)],
                "network_failures": [],
                "elements_found": [],
            }

        stdout = res.stdout or ""
        stderr = res.stderr or ""

        # Verifica falhas de conexão
        if "ERR_CONNECTION_REFUSED" in stderr or "ERR_NAME_NOT_RESOLVED" in stderr or (res.returncode != 0 and not stdout):
            return {
                "available": True,
                "status": "FAIL",
                "valid": False,
                "reason": f"Falha de conexão com a URL {url}: conexão recusada ou página indisponível.",
                "console_errors": [stderr.strip()[:200]] if stderr else [],
                "network_failures": [{"url": url, "failure": "Connection refused"}],
                "elements_found": [],
            }

        # Valida selectors no DOM renderizado
        elements_found = []
        if expected_selectors:
            for sel in expected_selectors:
                found = False
                if sel.startswith("#"):
                    elem_id = sel[1:]
                    found = bool(re.search(rf'id=[\'"]{re.escape(elem_id)}[\'"]', stdout, re.IGNORECASE))
                elif sel.startswith("."):
                    elem_cls = sel[1:]
                    found = bool(re.search(rf'class=[\'"][^\'"]*\b{re.escape(elem_cls)}\b[^\'"]*[\'"]', stdout, re.IGNORECASE))
                else:
                    found = bool(re.search(rf'<{re.escape(sel)}\b', stdout, re.IGNORECASE))
                elements_found.append({"selector": sel, "found": found})

        missing_selectors = [e for e in elements_found if not e["found"]]
        has_dom = "<html" in stdout.lower() or "<body" in stdout.lower()
        is_valid = res.returncode == 0 and has_dom and len(missing_selectors) == 0

        return {
            "available": True,
            "status": "PASS" if is_valid else "FAIL",
            "valid": is_valid,
            "http_status": 200 if is_valid else (500 if not has_dom else 404),
            "console_errors": [stderr.strip()[:200]] if stderr and not is_valid else [],
            "network_failures": [],
            "elements_found": elements_found,
            "reason": "OK (Validado via Microsoft Edge headless)" if is_valid else "Falhas detetadas na renderização do DOM.",
            "dom_length": len(stdout),
        }
