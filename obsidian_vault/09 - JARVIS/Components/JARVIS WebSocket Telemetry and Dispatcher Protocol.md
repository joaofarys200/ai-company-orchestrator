---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
difficulty: advanced
tags:
  - jarvis
  - websockets
  - telemetry
  - json-rpc
  - streaming
prerequisites:
  - "[[FastAPI and WebSocket Lifecycle Management]]"
  - "[[Structured Logging and Distributed Trace Context]]"
related:
  - "[[JARVIS Component Architecture]]"
  - "[[Credential Sanitization and Secret Masking]]"
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

# ðŸ“¡ JARVIS WebSocket Telemetry and Dispatcher Protocol

## 1. Purpose
O protocolo de telemetria WebSocket (`/ws/telemetry`) Ã© o canal full-duplex de comunicaÃ§Ã£o assÃ­ncrona entre o backend Python do JARVIS OS e a interface desktop do utilizador, transmitindo eventos de missÃµes, saÃ­das de terminal em streaming, mÃ©tricas de hardware e respostas de voz.

---

## 2. Responsibilities
- Transmitir eventos de progresso de missÃµes (`MISSION_PROGRESS`, `STEP_STARTED`, `STEP_COMPLETED`).
- Emitir telemetria de terminal em streaming com saÃ­da limpa de caracteres ANSI.
- Aplicar o filtro de saÃ­da obrigatÃ³rio de redaÃ§Ã£o de segredos (ver [[Lesson - Accidental Secret Leaks in Telemetry Broadcast]] e [[ADR-004 - Strict Exit Barrier Secret Sanitization in WebSocket Telemetry]]).
- Gerir conexÃµes concorrentes com heartbeats e reconexÃ£o automÃ¡tica.

---

## 3. Inputs & Outputs
- **Inputs**: Mensagens JSON-RPC de comandos do utilizador (`start_mission`, `pause_mission`, `voice_input`).
- **Outputs**: Payloads de eventos tipados em conformidade com [`websocket_schema.py`](file:///c:/Users/joaor/Desktop/JarvisOS/websocket_schema.py).

---

## 4. State Management & Invariants
- O `ConnectionManager` mantÃ©m um registo de WebSockets ativos e remove sockets desconectados de forma thread-safe.

---

## 5. Dependencies
- [`server.py`](file:///c:/Users/joaor/Desktop/JarvisOS/server.py)
- [`websocket_schema.py`](file:///c:/Users/joaor/Desktop/JarvisOS/websocket_schema.py)

---

## 6. Failure Modes & Recovery
- **Failure**: DesconexÃ£o abrupta do cliente ou sobrecarga de mensagens em buffer.
- **Recovery**: Descarte de mensagens volÃ¡teis e reconexÃ£o com envio do snapshot de estado atual.

---

## 7. Security Boundaries
- Exit Barrier de higienizaÃ§Ã£o de tokens aplicada em todo o broadcast.

---

## 8. Evidence Produced & Tests
- **Evidence**: Registos em `telemetry_logs`.
- **Tests**: `tests/test_server_websocket_characterization.py`, `tests/test_websocket_dispatcher_contract.py`.

---

## 9. Related Concepts
- [[FastAPI and WebSocket Lifecycle Management]]
- [[Structured Logging and Distributed Trace Context]]
- [[JARVIS Component Architecture]]

