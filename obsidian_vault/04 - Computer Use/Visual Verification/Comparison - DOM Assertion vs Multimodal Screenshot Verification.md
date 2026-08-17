---
type: comparison
domain: computer-use
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - computer-use
  - comparison
  - dom
  - visual-verification
  - playwright
  - multimodal
prerequisites:
  - "[[DOM State Inspection and Resilient Locators]]"
  - "[[Visual Regression and Screenshot Verification]]"
related:
  - "[[Computer Use Action Verification and Observable Evidence Matrix]]"
  - "[[How to Detect Failed Playwright Deployments]]"
used_by:
  - "[[JARVIS ComputerUseEngine and Playwright Integration]]"
failure_modes:
  - "[[Lesson - Hydration Race Condition in Fast Form Submit]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Playwright Assertions and Visual Comparisons (Microsoft)
    type: PRIMARY_SOURCE
    url: https://playwright.dev/docs/test-assertions
---

# ⚖️ Comparison: DOM Assertion vs Multimodal Screenshot Verification

## 1. Tabela Comparativa de Validação de Interface

| Dimensão | Asserção Programática de DOM (ARIA/Texto) | Verificação Visual por Screenshot Multimodal |
|---|---|---|
| **Custo de Computação / Tokens**| **Zero tokens (Executa localmente no nó Node/Python em $< 5\text{ms}$)** | Elevado (Requer modelo multimodal de visão como GPT-4o / Qwen-VL) |
| **Velocidade de Feedback** | **Instantânea ($< 10\text{ms}$)** | Lenta ($1500 - 4000\text{ms}$ por chamada de visão) |
| **Detecção de Bugs de Layout** | Cego a sobreposições visuais, quebra de CSS e elementos invisíveis | **Excelente (Detecta botões tapados, contraste ruim e cores erradas)** |
| **Determinismo** | **100% Determinístico e binário** | Parcialmente estocástico (Dependente da interpretação do modelo de visão) |

---

## 2. Decisão de Engenharia para o JARVIS

### When should JARVIS choose DOM Assertion?
- Em 90% dos passos de automação: validar se um formulário foi submetido, se um texto de sucesso apareceu ou se uma linha foi adicionada na tabela.

### When should JARVIS choose Multimodal Screenshot Verification?
- No final da criação de landing pages e interfaces: validar harmonia estética, contraste, ausência de quebras de layout responsivo e alinhamento de componentes.

### What failure mode does each introduce?
- **DOM Assertion**: Pode aprovar uma interface onde o botão está no DOM mas totalmente coberto por uma `div` invisível com `z-index: 9999`.
- **Screenshot Multimodal**: Alucinação ocasional do modelo de visão ou latência intolerável em loops rápidos de automação.

---

## 3. Related Concepts
- [[DOM State Inspection and Resilient Locators]]
- [[Visual Regression and Screenshot Verification]]
- [[Computer Use Action Verification and Observable Evidence Matrix]]
