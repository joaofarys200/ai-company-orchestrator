---
type: lesson
domain: jarvis
source: production
severity: medium
component: computer-use
status: verified
source_type: JARVIS_INTERNAL
confidence: high
tags:
  - jarvis
  - lesson
  - computer-use
  - playwright
  - race-conditions
prerequisites:
  - "[[Playwright Architecture and Automation Protocol]]"
  - "[[DOM State Inspection and Resilient Locators]]"
related:
  - "[[How to Detect and Fix Stale Element and Navigation Race Conditions]]"
  - "[[How to Detect Failed Playwright Deployments]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Indirect Prompt Injection via Web Pages]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS Incident Report - Incident INC-2026-08-11
    type: JARVIS_INTERNAL
    url: internal://incidents/INC-2026-08-11
---

# 📝 Lesson - Hydration Race Condition in Fast Form Submit

## 1. Failure
Num teste automatizado de validação de interface via Playwright, o agente preencheu um formulário de login e clicou no botão de submissão em menos de 150ms após o carregamento da página. O formulário não executou a requisição AJAX e a página foi recarregada com uma submissão HTTP GET tradicional vazia, gerando falso positivo de falha de autenticação.

---

## 2. Root Cause
1. **Hydration Lag em Frameworks SPA/SSR**: O servidor web serviu o HTML estático inicial instantaneamente, mas os manipuladores de evento JavaScript (`onSubmit={handleSubmit}`) do bundle React ainda não estavam vinculados aos elementos do DOM no momento do clique do agente.
2. **Ausência de Espera por Hidratação / Network Idle**: O agente utilizou `page.goto(url)` sem aguardar o evento de ciclo de vida de rede estável.

---

## 3. Why Existing Protection Failed
O Playwright verificou com sucesso que o botão estava anexado, visível e habilitado (*Actionability Checks*), mas o Playwright não consegue inspecionar nativamente se os event listeners assíncronos do React/Vue já foram vinculados via JavaScript.

---

## 4. Corrective Action
1. **Adição de Indicador de Prontidão no DOM**: Adicionar `wait_until="networkidle"` e aguardar explicitamente por atributos `data-hydrated="true"` ou pela resolução de fontes antes de submeter formulários críticos.
2. **Padrão de Promessa Concorrente**: Executar `async with page.expect_response(...)` antes do trigger do clique.

---

## 5. Generalizable Principle
> *Elementos HTML visíveis não significam lógica JavaScript hidratada. Em testes automatizados, aguarde sempre a prontidão funcional do runtime do frontend.*

---

## 6. Related Concepts
- [[How to Detect and Fix Stale Element and Navigation Race Conditions]]
- [[Playwright Architecture and Automation Protocol]]
- [[DOM State Inspection and Resilient Locators]]

---

## 7. Tests Added
- `tests/test_playwright_resilience.py::test_form_submission_waits_for_event_listeners`
