---
type: runbook
domain: computer-use
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: intermediate
tags:
  - runbook
  - computer-use
  - playwright
  - race-conditions
  - hydration
  - stale-element
prerequisites:
  - "[[Playwright Architecture and Automation Protocol]]"
  - "[[DOM State Inspection and Resilient Locators]]"
related:
  - "[[How to Detect Failed Playwright Deployments]]"
  - "[[Computer Use Action Verification and Observable Evidence Matrix]]"
used_by:
  - "[[JARVIS ComputerUseEngine and Playwright Integration]]"
failure_modes:
  - "[[Lesson - Hydration Race Condition in Fast Form Submit]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Playwright Auto-Waiting and Navigation Guide (Microsoft)
    type: PRIMARY_SOURCE
    url: https://playwright.dev/docs/navigations
---

# 🛠️ Como Lidar com Race Conditions de Hidratacao em Submissao de Formularios e Stale Elements

## 1. Critérios de Sucesso e Falha
- **Critério de Sucesso**: O clique no botão ou submissão de formulário ocorre após a hidratação completa dos manipuladores JavaScript, disparando o evento AJAX/SPA esperado sem reload acidental ou erro `stale element reference`.
- **Critério de Falha**: O teste falha por `Element is not attached to DOM` ou o formulário é submetido em branco por GET tradicional antes da hidratação.

---

## 2. Diagnóstico
1. Se o Playwright lança `stale element`, o DOM foi reconstruído pelo framework frontend (React/Vue/Svelte) enquanto o locator realizava a ação.
2. Se a submissão recarrega a página em vez de chamar a API, houve **Hydration Lag** (ver [[Lesson - Hydration Race Condition in Fast Form Submit]]).

---

## 3. Procedimento Operacional de Resolução

### Passo 1: Utilizar Promessa Concorrente `expect_response`
```python
async with page.expect_response(lambda r: "/api/submit" in r.url and r.status == 200) as response_info:
    await page.get_by_role("button", name="Salvar").click()
response = await response_info.value
```

### Passo 2: Aguardar Atributo de Hidratação
```python
await page.wait_for_selector("body[data-hydrated='true']")
```

---

## 4. Related Concepts
- [[Playwright Architecture and Automation Protocol]]
- [[DOM State Inspection and Resilient Locators]]
- [[Lesson - Hydration Race Condition in Fast Form Submit]]
