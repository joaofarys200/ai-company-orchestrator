---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: evolving
difficulty: advanced
tags:
  - jarvis
  - gemini-live
  - multimodal
  - websockets
  - bidi-streaming
  - voice
prerequisites:
  - "[[FastAPI and WebSocket Lifecycle Management]]"
  - "[[JARVIS Voice Service and Audio Streaming Architecture]]"
related:
  - "[[JARVIS Model Harness Implementation]]"
  - "[[JARVIS Component Architecture]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS Codebase - gemini_live.py
    type: JARVIS_INTERNAL
    url: internal://gemini_live.py
---

# 🌐 JARVIS Gemini Live Multimodal WebSocket Protocol

## 1. Purpose
O `GeminiLiveService` gerencia a sessão de streaming bidirecional em tempo real (*Bidi WebSocket*) com a API Multimodal Live do Gemini, permitindo conversação por voz de baixíssima latência ($< 500\text{ms}$), interrupção natural de fala (*Barge-in*) e invocação de ferramentas em tempo de execução.

---

## 2. Responsibilities
- Estabelecer conexão WebSocket persistente autenticada via `GEMINI_API_KEY`.
- Serializar áudio do microfone em base64 e transmiti-lo em tempo real (`realtime_input`).
- Processar mensagens do servidor (`server_content`, `model_turn`, `audio_chunk`, `tool_call`).
- Detetar interrupções do utilizador (Barge-in) via WebRTC VAD local e limpar instantaneamente a fila de reprodução de áudio do modelo.
- Executar chamadas de função locais autorizadas (`VOICE_CONTROL_TOOLS`) e devolver respostas estruturadas ao modelo.

---

## 3. Inputs & Outputs
- **Inputs**: Áudio de microfone em PCM int16 (16kHz ou 24kHz), comandos de cancelamento.
- **Outputs**: Áudio recebido do modelo em PCM 24kHz enviado diretamente para o dispositivo de saída via `sounddevice.OutputStream`.

---

## 4. State Management & Invariants
- Máquina de estados interna: `DISCONNECTED` $\rightarrow$ `CONNECTING` $\rightarrow$ `SESSION_READY` $\rightarrow$ `STREAMING` $\rightarrow$ `RECONNECTING`.
- Quando o VAD local detecta fala enquanto o modelo está a responder, o método `_handle_barge_in()` descarta os frames pendentes no buffer de áudio de saída em menos de $10\text{ms}$.

---

## 5. Dependencies
- [`gemini_live.py`](file:///c:/Users/joaor/Desktop/JarvisOS/gemini_live.py)
- Bibliotecas: `websockets`, `sounddevice`, `webrtcvad`, `numpy`, `asyncio`.

---

## 6. Execution Flow
```
[ Microfone: sounddevice ] -> Frames PCM -> [ Bidi WebSocket Uplink ] -> [ Gemini Live API ]
                                                                                   |
                                      +--------------------------------------------+
                                      | (Model Turn Audio Streaming)
                                      v
 [ Audio Queue ] -> [ sounddevice.OutputStream (24kHz) ] -> [ Caixas de Som ]
        |
 (Barge-in VAD Trigger) -> Limpa Audio Queue Atomicamente
```

---

## 7. Failure Modes & Recovery
- **Failure**: Desconexão de rede ou timeout de sessão do WebSocket da nuvem.
- **Recovery**: Reconexão com backoff exponencial e reenvio da configuração de setup da sessão.

---

## 8. Security Boundaries
- Isolamento de chaves secretas e execução restrita de ferramentas de voz (apenas ferramentas listadas em `VOICE_CONTROL_TOOLS` são aceites).

---

## 9. Evidence Produced & Tests
- **Evidence**: Registos estruturados em `gemini_live_logs`.
- **Tests**: `tests/test_gemini_live.py`.

---

## 10. Configuration & Performance Constraints
- Modelo padrão: `gemini-2.0-flash-exp`.
- Latência de ida e volta (RTT): $300 - 600\text{ms}$ dependendo da conectividade.

---

## 11. Related Concepts
- [[JARVIS Voice Service and Audio Streaming Architecture]]
- [[FastAPI and WebSocket Lifecycle Management]]
- [[Model Harness Architecture]]
