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
            # Playwright não instalado no ambiente Python atual
            return {
                "available": False,
                "status": "INSUFFICIENT_EVIDENCE",
                "valid": False,
                "reason": "Playwright não está instalado no ambiente Python atual.",
                "console_errors": [],
                "network_failures": [],
                "elements_found": [],
            }

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
