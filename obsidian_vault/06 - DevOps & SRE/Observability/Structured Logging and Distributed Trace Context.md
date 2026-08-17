---
type: concept
domain: devops
difficulty: intermediate
tags:
  - devops
  - observability
  - structured-logging
  - tracing
  - opentelemetry
status: verified
---

# 📝 Structured Logging and Distributed Trace Context

## 1. Do Logging em Texto Livre ao JSON Estruturado
Logs em texto livre (ex: `print("Erro ao processar ficheiro " + str(f))`) são difíceis de pesquisar por máquinas e impossíveis de agregar estatisticamente.

O **Logging Estruturado** emite cada entrada como um objeto JSON válido contendo metadados essenciais para análise automática por agentes e indexadores (Elasticsearch, Loki, Datadog).

```json
{
  "timestamp": "2026-08-17T19:35:00.123Z",
  "level": "ERROR",
  "logger": "jarvis.patch_engine",
  "message": "Falha na aplicação do patch cirúrgico",
  "mission_id": "mis-102",
  "agent": "Devon",
  "file_path": "backend/server.py",
  "error_type": "SyntaxError",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7"
}
```

---

## 2. Propagação de Contexto W3C TraceContext (`traceparent`)

Em sistemas assíncronos e distribuídos, um pedido que passa do Frontend $\rightarrow$ FastAPI $\rightarrow$ Swarm Orchestrator $\rightarrow$ Sandbox de Código deve partilhar o mesmo identificador de trace (**Trace ID**).

O padrão W3C TraceContext define o header:
`traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
- `00`: Versão do formato.
- `4bf92f3577b34da6a3ce929d0e0e4736`: Trace ID global único de 128 bits.
- `00f067aa0ba902b7`: Span ID da operação atual de 64 bits.
- `01`: Flags de amostragem (*Sampled*).

---

## 3. Implementação em Python com ContextVars

```python
import logging
import json
import uuid
from contextvars import ContextVar
from typing import Any

current_trace_id: ContextVar[str] = ContextVar("current_trace_id", default="")

class JSONTraceFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": current_trace_id.get() or "none",
            "file": record.filename,
            "line": record.lineno
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)
```

---

## 4. Related Concepts
- [[SLI-SLO Metrics and Error Budgets]]
- [[Healthchecks and Circuit Breakers]]
- [[Credential Sanitization and Secret Masking]]

---

## 5. Sources
- *W3C Recommendation - Trace Context*: https://www.w3.org/TR/trace-context/
- *OpenTelemetry Python Documentation*: https://opentelemetry.io/docs/languages/python/
