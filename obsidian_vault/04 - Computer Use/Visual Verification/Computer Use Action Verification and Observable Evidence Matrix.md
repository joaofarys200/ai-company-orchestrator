---
type: reference
domain: computer-use
status: verified
source_type: SYNTHESIZED
confidence: high
difficulty: advanced
tags:
  - computer-use
  - playwright
  - action-verification
  - observable-evidence
  - visual-validation
prerequisites:
  - "[[Playwright Architecture and Automation Protocol]]"
  - "[[DOM State Inspection and Resilient Locators]]"
related:
  - "[[Browser Network Interception and Mocking]]"
  - "[[Visual Regression and Screenshot Verification]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Hydration Race Condition in Fast Form Submit]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Playwright Auto-Waiting and Assertions Documentation (Microsoft)
    type: PRIMARY_SOURCE
    url: https://playwright.dev/docs/actionability
---

# 🌐 Computer Use Action Verification and Observable Evidence Matrix

Esta matriz estabelece o protocolo de verificação em duas etapas (**Ação $\rightarrow$ Evidência Observável**) para agentes de automação web, eliminando falsos positivos e ações cegas no navegador.

---

## 1. Matriz de Ação e Evidência Observável

| Ação do Agente | Resultado Esperado | Evidência Observável Obrigatória | Deteção de Falha | Ação de Recuperação |
|---|---|---|---|---|
| **`click(button)`** | Disparo de submissão de formulário ou modal aberto | URL alterada, resposta de rede HTTP 200/201, ou elemento filho presente no DOM | Timeout de rede ou ausência de novo estado visual | Aguardar hidratação (`data-hydrated="true"`) e retentar clique |
| **`fill(input, text)`** | Texto inserido no campo de formulário | `input.input_value() == text` verificado via DOM | Campo permanece vazio após preenchimento (React state override) | Utilizar `page.keyboard.type()` com atraso entre teclas |
| **`navigate(url)`** | Página carregada com layout funcional | `page.wait_for_load_state("networkidle")` e `h1` visível | Tela branca ou `pageerror` não tratado no console | Capturar screenshot, inspecionar console logs e dar reload |
| **`download_file()`** | Ficheiro gravado em disco no diretório temporário | Evento `page.expect_download()` resolvido com tamanho $> 0$ bytes | Timeout de download ou ficheiro de 0 bytes | Inspecionar status HTTP da rota de download |
| **`authenticate()`** | Sessão de usuário ativa | Cookie de sessão presente ou elemento `profile-menu` visível | Redirecionamento de volta para `/login?error=1` | Verificar credenciais e limpar storage antes de retentar |

---

## 2. Related Concepts
- [[Playwright Architecture and Automation Protocol]]
- [[DOM State Inspection and Resilient Locators]]
- [[Lesson - Hydration Race Condition in Fast Form Submit]]
