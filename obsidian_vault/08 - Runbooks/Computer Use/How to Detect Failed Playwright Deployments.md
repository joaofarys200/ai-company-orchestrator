---
type: troubleshooting
domain: computer-use
difficulty: intermediate
tags:
  - computer-use
  - troubleshooting
  - playwright
  - deployment-validation
  - console-errors
status: verified
---

# 🛠️ How to Detect Failed Playwright Deployments

## 1. Sintomas & Diagnóstico
- O servidor web responde com código `200 OK`, mas a página exibe uma tela branca em branco (*White Screen of Death*).
- O agente conclui a missão reportando "sucesso" sem perceber que os scripts JS falharam no bundling (`Uncaught ReferenceError` ou `ChunkLoadError`).
- Erros de CORS no console bloqueiam o carregamento de dados essenciais da API.

---

## 2. Diagnóstico Automatizado de Deployments (Smoke Runner)

```python
from playwright.async_api import async_playwright
from dataclasses import dataclass
from typing import List

@dataclass
class DeploymentHealthResult:
    is_healthy: bool
    status_code: int
    console_errors: List[str]
    uncaught_exceptions: List[str]
    failed_network_requests: List[str]

async def audit_web_deployment(url: str, timeout_ms: int = 15000) -> DeploymentHealthResult:
    console_errors = []
    uncaught_exceptions = []
    failed_requests = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # 1. Escutar logs de console
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # 2. Escutar exceções não tratadas da página
        page.on("pageerror", lambda exc: uncaught_exceptions.append(str(exc)))

        # 3. Escutar falhas de requisição HTTP (4xx, 5xx)
        page.on("requestfailed", lambda req: failed_requests.append(f"{req.method} {req.url}: {req.failure}"))

        response = await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        status_code = response.status if response else 0

        await browser.close()

    is_healthy = (
        status_code == 200 and
        len(uncaught_exceptions) == 0 and
        len(console_errors) == 0
    )

    return DeploymentHealthResult(
        is_healthy=is_healthy,
        status_code=status_code,
        console_errors=console_errors,
        uncaught_exceptions=uncaught_exceptions,
        failed_network_requests=failed_requests
    )
```

---

## 3. Ações de Correção Imediata
1. Se `uncaught_exceptions` contiver `ChunkLoadError`: Reconstruir os assets estáticos (`npm run build`).
2. Se `console_errors` contiver `CORS policy`: Verificar os headers `Access-Control-Allow-Origin` no backend FastAPI.

---

## 4. Related Concepts
- [[Playwright Architecture and Automation Protocol]]
- [[Browser Network Interception and Mocking]]
- [[Visual Regression and Screenshot Verification]]

---

## 5. Sources
- *Playwright Page Events Documentation*: https://playwright.dev/python/docs/api/class-page#page-event-page-error
- *Google Chrome DevTools - Console Error Analysis*: https://developer.chrome.com/docs/devtools/console/
