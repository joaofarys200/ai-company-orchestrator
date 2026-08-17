---
type: technology
domain: computer-use
difficulty: intermediate
tags:
  - computer-use
  - browser-automation
  - playwright
  - cdp
  - testing
status: verified
---

# 🎭 Playwright Architecture and Automation Protocol

## 1. O que é & Arquitetura de Comunicação
O **Playwright** (Microsoft) é uma biblioteca e framework de automação de navegadores modernos (Chromium, Firefox, WebKit) projetada para testes ponta-a-ponta resilientes, scraping avançado e capacidades de *Computer Use* por agentes de IA.

Ao contrário de abordagens legadas como o Selenium (que dependia de drivers intermediários HTTP WebDriver com polling lento), o Playwright comunica-se **diretamente via WebSockets bidirecionais** com o protocolo interno do navegador (Chrome DevTools Protocol - **CDP** no Chromium).

```
+-------------------------------------------------------------+
|                 JARVIS OS / Python Subagent                 |
+------------------------------+------------------------------+
                               | WebSocket IPC (JSON-RPC)
                               v
+-------------------------------------------------------------+
|                 Playwright Driver (Node.js)                 |
|   +-------------------------------------------------------+ |
|   | Browser Server (Chromium / Firefox / WebKit)          | |
|   |   +-------------------------------------------------+ | |
|   |   | BrowserContext 1 (Cookies, Cache, Storage Isol.)| | |
|   |   |   +------------------+   +--------------------+ | | |
|   |   |   | Page / Tab 1     |   | Page / Tab 2       | | | |
|   |   |   +------------------+   +--------------------+ | | |
|   |   +-------------------------------------------------+ | |
|   +-------------------------------------------------------+ |
+-------------------------------------------------------------+
```

---

## 2. Conceitos Nucleares de Isolamento

1. **Browser**: A instância de processo executável do navegador (`chromium.launch(headless=True)`).
2. **BrowserContext**: Uma sessão incognita totalmente isolada em memória (sem partilha de cookies, localStorage ou cache com outros contextos). Permite simular múltiplos utilizadores em paralelo sem reabrir o processo do browser.
3. **Page**: Uma aba individual dentro de um `BrowserContext`.

---

## 3. Auto-Waiting e Ações Acionáveis (Actionability Checks)
Antes de executar qualquer ação (`click`, `fill`, `hover`), o Playwright executa automaticamente 5 verificações sem necessidade de `sleep()` manual:
- O elemento está anexado ao DOM (*Attached*);
- O elemento está visível (*Visible*);
- O elemento é estável (*Stable* - sem animações CSS ativas);
- O elemento recebe eventos (*Receives Events* - não sobreposto por modais);
- O elemento está habilitado (*Enabled* - não desativado por `disabled`).

---

## 4. Implementação Padrão em Python Async

```python
from playwright.async_api import async_playwright
import asyncio

async def inspect_web_page_safely(url: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisOS/1.0"
        )
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        try:
            response = await page.goto(url, wait_until="networkidle", timeout=15000)
            status_code = response.status if response else 0
            title = await page.title()
            screenshot_bytes = await page.screenshot(full_page=False)
            
            return {
                "status_code": status_code,
                "title": title,
                "console_errors": console_errors,
                "screenshot_size": len(screenshot_bytes)
            }
        finally:
            await context.close()
            await browser.close()
```

---

## 5. Related Concepts
- [[DOM State Inspection and Resilient Locators]]
- [[Browser Network Interception and Mocking]]
- [[Indirect Prompt Injection via Web Pages]]
- [[How to Detect and Fix Stale Element and Navigation Race Conditions]]

---

## 6. Sources
- *Playwright Official Documentation (Microsoft)*: https://playwright.dev/python/docs/intro
- *Chrome DevTools Protocol (CDP) Specification*: https://chromedevtools.github.io/devtools-protocol/
