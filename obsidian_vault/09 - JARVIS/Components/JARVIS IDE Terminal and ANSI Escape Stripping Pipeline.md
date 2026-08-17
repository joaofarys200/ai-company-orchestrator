---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
difficulty: intermediate
tags:
  - jarvis
  - terminal
  - ansi-stripper
  - websockets
  - telemetry
prerequisites:
  - "[[JARVIS WebSocket Telemetry and Dispatcher Protocol]]"
related:
  - "[[Credential Sanitization and Secret Masking]]"
  - "[[FastAPI and WebSocket Lifecycle Management]]"
used_by:
  - "[[JARVIS System Architecture]]"
failure_modes:
  - "[[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS Codebase - server.py and websocket_schema.py
    type: JARVIS_INTERNAL
    url: internal://server.py
---

# ðŸ–¥ï¸ JARVIS IDE Terminal and ANSI Escape Stripping Pipeline

## 1. Purpose
O pipeline de terminal da IDE gerencia a captura de stdout/stderr de comandos de compilaÃ§Ã£o, testes e ferramentas executados na sandbox, higienizando caracteres de controle ANSI e transmitindo o fluxo limpo em tempo real para o frontend desktop.

---

## 2. Responsibilities
- Capturar a saÃ­da contÃ­nua de subprocessos sem travar em buffers de terminal (*Unbuffered I/O*).
- Aplicar expressÃµes regulares para remover sequÃªncias de escape ANSI de cores e posicionamento de cursor (`\x1b\[[0-9;]*[a-zA-Z]`) antes de enviar aos modelos ou salvar no histÃ³rico.
- Preservar a formataÃ§Ã£o textual limpa nos eventos `TERMINAL_OUTPUT`.
- Interceptar e mascarar segredos no pipeline de saÃ­da antes do broadcast WebSocket.

---

## 3. Inputs & Outputs
- **Inputs**: Streams de bytes brutos de pipes de subprocessos (`stdout`, `stderr`).
- **Outputs**: Payloads de texto UTF-8 normalizados e decodificados em conformidade com [`websocket_schema.py`](file:///c:/Users/joaor/Desktop/JarvisOS/websocket_schema.py).

---

## 4. Dependencies
- [`server.py`](file:///c:/Users/joaor/Desktop/JarvisOS/server.py)
- [`sandbox.py`](file:///c:/Users/joaor/Desktop/JarvisOS/sandbox.py)

---

## 5. Failure Modes & Recovery
- **Failure**: SaÃ­da excessivamente longa (megabytes de logs de compilaÃ§Ã£o) saturando o canal WebSocket.
- **Recovery**: Janela deslizante de truncamento com resumo de Ãºltimas 500 linhas.

---

## 6. Related Concepts
- [[JARVIS WebSocket Telemetry and Dispatcher Protocol]]
- [[Credential Sanitization and Secret Masking]]
- [[FastAPI and WebSocket Lifecycle Management]]

