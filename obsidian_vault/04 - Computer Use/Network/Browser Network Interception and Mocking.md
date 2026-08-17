---
type: concept
domain: computer-use
difficulty: intermediate
tags:
  - computer-use
  - playwright
  - network
  - mocking
  - testing
status: verified
---

# 🌐 Browser Network Interception and Mocking

## 1. Definição & Casos de Uso
A **Interceção de Rede (Network Routing / Interception)** no Playwright permite monitorizar, modificar, simular respostas ou bloquear requisições HTTP/WebSocket emitidas pelo navegador em tempo real.

Casos de uso essenciais:
1. **Mocking de APIs Externas Pagas**: Testar fluxos de checkout sem emitir cobranças reais.
2. **Simulação de Falhas e Degradação de Rede**: Testar como o frontend reage a erros `500 Internal Server Error`, `429 Rate Limit` ou latências de 10 segundos.
3. **Bloqueio de Rastreadores e Imagens**: Acelerar scraping e testes descartando downloads pesados (`.png`, `.jpg`, `.woff2`, scripts de analytics).

---

## 2. Padrão de Roteamento e Mocking (Python Async)

```python
from playwright.async_api import Page, Route

async def configure_network_interceptions(page: Page):
    # 1. Bloquear imagens e fontes para acelerar a execução do agente em 80%
    await page.route(
        "**/*.{png,jpg,jpeg,svg,woff,woff2,gif}",
        lambda route: route.abort()
    )

    # 2. Mockar endpoint de dados do usuário
    async def handle_user_api(route: Route):
        mock_payload = {
            "user_id": "usr_test_99",
            "name": "Devon Agent",
            "role": "SYSTEM_BUILDER",
            "credits": 5000
        }
        await route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(mock_payload)
        )

    await page.route("**/api/v1/user/profile", handle_user_api)
```

---

## 3. Captura e Asserção de Payloads Enviados

```python
async def assert_form_submission_payload(page: Page):
    async with page.expect_request("**/api/v1/mission/submit") as first:
        await page.get_by_role("button", name="Submeter").click()
    
    request = await first.value
    post_data = request.post_data_json
    assert post_data["priority"] == "HIGH"
```

---

## 4. Related Concepts
- [[Playwright Architecture and Automation Protocol]]
- [[DOM State Inspection and Resilient Locators]]
- [[How to Detect Failed Playwright Deployments]]

---

## 5. Sources
- *Playwright Network Mocking Guide*: https://playwright.dev/python/docs/network
- *RFC 9110 - HTTP Semantics*: https://datatracker.ietf.org/doc/html/rfc9110
