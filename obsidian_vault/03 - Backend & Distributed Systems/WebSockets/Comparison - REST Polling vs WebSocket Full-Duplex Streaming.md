---
type: comparison
domain: backend-systems
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: intermediate
tags:
  - backend
  - networking
  - comparison
  - rest-polling
  - websockets
  - streaming
prerequisites:
  - "[[FastAPI and WebSocket Lifecycle Management]]"
  - "[[JARVIS WebSocket Telemetry and Dispatcher Protocol]]"
related:
  - "[[Structured Logging and Distributed Trace Context]]"
  - "[[TCP Handshake and BBR Congestion Control]]"
used_by:
  - "[[JARVIS System Architecture]]"
failure_modes:
  - "[[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: RFC 6455 - The WebSocket Protocol
    type: PRIMARY_SOURCE
    url: https://datatracker.ietf.org/doc/html/rfc6455
---

# âš–ï¸ Comparison: REST Polling vs WebSocket Full-Duplex Streaming

## 1. Tabela Comparativa de Comunicação em Tempo Real

| Dimensão | Short / Long Polling HTTP/REST | WebSocket Full-Duplex (RFC 6455) |
|---|---|---|
| **Estabelecimento de Conexão** | Nova conexão TCP/TLS e headers HTTP a cada requisição | **Upgrade único com handshake TCP persistente** |
| **Overhead de Headers** | 500 - 1500 bytes de cabeçalhos HTTP por polling | **Apenas 2 a 10 bytes de framing por mensagem** |
| **Latência de Notificação** | Limitada pelo intervalo de polling ($1 - 5\text{s}$) | **Sub-milissegundo instantâneo ($< 10\text{ms}$)** |
| **Suporte a Streaming Bidirecional**| Não (Cliente sempre inicia a requisição) | **Sim (Servidor e cliente transmitem simultaneamente)** |

---

## 2. Decisão de Engenharia para o JARVIS

### When should JARVIS choose REST Polling?
- Para endpoints administrativos esporádicos ou operações idempotentes de consulta simples (ex: `GET /health` ou `GET /version`).

### When should JARVIS choose WebSockets?
- Para streaming de telemetria de terminal, progresso de passos de missões em tempo real e sessões de áudio contínuo.

### What failure mode does each introduce?
- **REST Polling**: Desperdício massivo de CPU e I/O de rede com requisições vazias repetitivas.
- **WebSockets**: Dificuldade em balancear conexões com stateful proxies e risco de conexões zumbis se não houver heartbeats (*Ping/Pong frames*).

---

## 3. Related Concepts
- [[FastAPI and WebSocket Lifecycle Management]]
- [[JARVIS WebSocket Telemetry and Dispatcher Protocol]]
- [[TCP Handshake and BBR Congestion Control]]

