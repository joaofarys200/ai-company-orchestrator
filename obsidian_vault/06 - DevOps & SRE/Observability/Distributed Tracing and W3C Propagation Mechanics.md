---
type: concept
domain: devops
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - devops
  - tracing
  - opentelemetry
  - w3c
  - observability
prerequisites:
  - "[[Structured Logging and Distributed Trace Context]]"
related:
  - "[[FastAPI and WebSocket Lifecycle Management]]"
  - "[[Message Queues and Event-Driven Architectures]]"
used_by:
  - "[[JARVIS Component Architecture]]"
failure_modes:
  - "[[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]"
implementation:
  - "[[JARVIS System Architecture]]"
sources:
  - title: W3C Recommendation - Trace Context
    type: PRIMARY_SOURCE
    url: https://www.w3.org/TR/trace-context/
---

# 🛰️ Distributed Tracing and W3C Propagation Mechanics

## 1. Pergunta Central
> *Como correlacionar spans de execução assíncronos que atravessam fronteiras de rede (HTTP, WebSockets, subprocessos locais e agentes de IA) num único grafo de rastreabilidade de ponta a ponta?*

---

## 2. A Anatomia do Cabeçalho W3C `traceparent`

```text
version -            trace_id                  -    parent_id     - trace_flags
   00   - 4bf92f3577b34da6a3ce929d0e0e4736 - 00f067aa0ba902b7 -     01
```

- **`trace_id` (16 bytes / 32 hex chars)**: Identifica globalmente a missão inteira desde a requisição do usuário.
- **`parent_id` (8 bytes / 16 hex chars)**: Identifica o span pai imediato que chamou o subprocesso ou serviço atual.
- **`trace_flags` (8 bits)**: `01` indica que o trace foi amostrado (*Recorded*).

---

## 3. Injeção e Extração de Contexto em Python

```python
from contextvars import ContextVar
import uuid

trace_context: ContextVar[dict] = ContextVar("trace_context", default={})

def inject_w3c_traceparent() -> str:
    ctx = trace_context.get()
    trace_id = ctx.get("trace_id", uuid.uuid4().hex)
    span_id = uuid.uuid4().hex[:16]
    return f"00-{trace_id}-{span_id}-01"

def extract_w3c_traceparent(header_val: str) -> dict:
    parts = header_val.split("-")
    if len(parts) == 4 and parts[0] == "00":
        return {"trace_id": parts[1], "parent_span_id": parts[2]}
    return {"trace_id": uuid.uuid4().hex, "parent_span_id": None}
```

---

## 4. Related Concepts
- [[Structured Logging and Distributed Trace Context]]
- [[SLI-SLO Metrics and Error Budgets]]
- [[FastAPI and WebSocket Lifecycle Management]]
