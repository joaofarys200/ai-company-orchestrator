---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
difficulty: advanced
tags:
  - jarvis
  - computer-use
  - playwright
  - browser-automation
  - visual-validation
prerequisites:
  - "[[Playwright Architecture and Automation Protocol]]"
  - "[[DOM State Inspection and Resilient Locators]]"
related:
  - "[[Computer Use Action Verification and Observable Evidence Matrix]]"
  - "[[Visual Regression and Screenshot Verification]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Hydration Race Condition in Fast Form Submit]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS Codebase - Playwright Tools and Computer Use Engine
    type: JARVIS_INTERNAL
    url: internal://agents/tools.py
---

# 🌐 JARVIS ComputerUseEngine and Playwright Integration

## 1. Purpose
O `ComputerUseEngine` fornece a camada de automação de navegador web para agentes do JARVIS OS, permitindo navegação interativa, extração de DOM, validação visual de interfaces e submissão de formulários via Playwright.

---

## 2. Responsibilities
- Gerir o ciclo de vida do navegador Chromium em modo headless/headful.
- Isolar sessões através de `BrowserContext` independentes com cookies limpos.
- Executar ações de clique, digitação, rolagem e captura de screenshots com auto-waiting.
- Interceptar tráfego de rede e capturar erros não tratados de console (`pageerror`).

---

## 3. Inputs & Outputs
- **Inputs**: Comandos de navegação (`goto`, `click_element`, `fill_form`, `take_screenshot`).
- **Outputs**: Árvores de acessibilidade (ARIA snapshot), screenshots PNG, logs de rede e console.

---

## 4. State Management & Invariants
- Toda a ação é acompanhada por verificação observável pós-ação (ver [[Computer Use Action Verification and Observable Evidence Matrix]]).

---

## 5. Dependencies
- Biblioteca Playwright Python assíncrona (`playwright.async_api`).
- [`agents/tools.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/tools.py)

---

## 6. Failure Modes & Recovery
- **Failure**: Elemento stale ou race condition de hidratação (ver [[Lesson - Hydration Race Condition in Fast Form Submit]]).
- **Recovery**: Re-tentativa com espera explícita por `networkidle` e locators por papel ARIA.

---

## 7. Security Boundaries
- Bloqueio de download de arquivos executáveis não verificados e desativação de permissões de microfone/câmera não autorizadas no navegador.

---

## 8. Evidence Produced & Tests
- **Evidence**: Screenshots no diretório de artefatos, HAR logs de rede.
- **Tests**: `tests/test_playwright_resilience.py`.

---

## 9. Related Concepts
- [[Playwright Architecture and Automation Protocol]]
- [[Computer Use Action Verification and Observable Evidence Matrix]]
- [[DOM State Inspection and Resilient Locators]]
