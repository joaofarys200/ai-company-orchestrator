---
type: concept
domain: computer-use
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: intermediate
tags:
  - computer-use
  - playwright
  - dom
  - aria
  - resilient-locators
  - web-testing
prerequisites:
  - "[[Playwright Architecture and Automation Protocol]]"
related:
  - "[[Visual Regression and Screenshot Verification]]"
  - "[[Computer Use Action Verification and Observable Evidence Matrix]]"
  - "[[How to Detect and Fix Stale Element and Navigation Race Conditions]]"
used_by:
  - "[[JARVIS ComputerUseEngine and Playwright Integration]]"
failure_modes:
  - "[[Lesson - Hydration Race Condition in Fast Form Submit]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: W3C WAI-ARIA 1.2 Specification (Role and Accessible Name Computation)
    type: PRIMARY_SOURCE
    url: https://www.w3.org/TR/wai-aria-1.2/
  - title: Playwright Best Practices - Locators (Microsoft)
    type: PRIMARY_SOURCE
    url: https://playwright.dev/docs/locators
---

# 🎯 DOM State Inspection e Seletores Resilientes Baseados em Papeis ARIA vs CSS Fragil

## 1. Pergunta Central
> *Por que seletores CSS estruturais ou XPath absolutos quebram com facilidade durante refatorações de frontend e como a árvore de acessibilidade (ARIA roles) fornece seletores resilientes e Ã  prova de mudanças cosméticas?*

---

## 2. A Hierarquia de Resiliência de Seletores

```
+-----------------------------------------------------------------------+
|  MÁXIMA RESILIÃŠNCIA (Orientado a Acessibilidade / Semântica Humana)  |
|  - `page.get_by_role("button", name="Submeter Pedido")`              |
|  - `page.get_by_label("Endereço de Email")`                          |
|  - `page.get_by_test_id("submit-order-btn")`                         |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|  MÉDIA RESILIÃŠNCIA (Orientado a Texto e Placeholders)                 |
|  - `page.get_by_placeholder("nome@empresa.com")`                     |
|  - `page.get_by_text("Confirmar Pagamento")`                          |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|  FRÁGIL / ANTI-PATTERN (Orientado a Estrutura DOM e Classes CSS)      |
|  - `page.locator("div.css-1234 > button.btn-primary")`                |
|  - `page.locator("/html/body/div[2]/form/div[3]/button")`             |
+-----------------------------------------------------------------------+
```

---

## 3. Invariantes de Inspeção do DOM no Playwright
1. **Auto-Waiting em Ações**: O Playwright aguarda automaticamente que o elemento esteja visível, estável e habilitado.
2. **Prioridade a Papéis ARIA**: Agentes utilizam primordialmente `get_by_role` com atributos de acessibilidade.

---

## 4. Related Concepts
- [[Playwright Architecture and Automation Protocol]]
- [[Computer Use Action Verification and Observable Evidence Matrix]]
- [[How to Detect and Fix Stale Element and Navigation Race Conditions]]

## Query Relevance
Seletores resilientes baseados em papéis aria vs css frágil no Playwright.

