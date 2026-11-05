---
type: concept
domain: software-engineering
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - software-engineering
  - python
  - asyncio
  - concurrency
  - event-loop
  - backpressure
---

# ⚡ Python Asyncio Event Loop Internals, Backpressure and Thread Offloading

## 1. Modelo Cooperativo de Single-Thread Event Loop
O `asyncio` em Python executa corrotinas cooperativamente numa **única thread de SO** multiplexando sockets não-bloqueantes (`epoll` / `IOCP` no Windows). Uma corrotina só cede o controlo num ponto explícito de `await`.

**Invariante Crítica de Latência**: Qualquer operação síncrona bloqueante (`requests.post`, `time.sleep`, parsing pesado de PDF/PyMuPDF, hashing/OCR ou queries SQLite longas) executada diretamente dentro de `async def` congela **100% dos WebSockets, heartbeats e timers** do servidor durante toda a sua duração.

---

## 2. Regras de Offloading e Concorrência Estruturada

| Tipo de Carga | Primitiva Correta | Anti-Padrão Perigoso |
|---|---|---|
| **I/O de Rede / Subprocesso** | `httpx.AsyncClient`, `asyncio.create_subprocess_exec` | `subprocess.run` / `requests` direto na corrotina |
| **I/O de Disco / C-Extension (GIL libertado)** | `await asyncio.to_thread(fn, *args)` | Executar leitura/escrita pesada no loop principal |
| **CPU-Bound Puro em Python (GIL retido)** | `loop.run_in_executor(ProcessPoolExecutor, ...)` | Dezenas de `to_thread` disputando o mesmo GIL |
| **Fan-Out Concorrente Delimitado** | `asyncio.TaskGroup` + `asyncio.Semaphore(N)` | `asyncio.gather(*milhares)` sem limite de memória/FD |

---

## 3. Semântica de Cancelamento e Limpeza Segura
`asyncio.CancelledError` herda de `BaseException` (Python 3.8+) para não ser engolida acidentalmente por `except Exception:`. Ao capturar cancelamento para libertar locks/leases, **é obrigatório relançar (`raise`)** a exceção, exceto na fronteira raiz da tarefa.

```python
import asyncio
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")

async def run_bounded_blocking(fn: Callable[[T], object], items: Iterable[T], limit: int = 4) -> list:
    sem = asyncio.Semaphore(limit)

    async def _worker(item: T) -> object:
        async with sem:
            return await asyncio.to_thread(fn, item)

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(_worker(x)) for x in items]
    return [t.result() for t in tasks]
```

---

## 4. Conceitos Relacionados & Fontes
- [[FastAPI and WebSocket Lifecycle Management]]
- [[Optimistic vs Pessimistic Locking]]
- [[Backpressure, Load Shedding and Little's Law in Async Pipelines]]
- [[Runbook - How to Recover from Worker Thrashing and CPU Throttling]]
- **Fontes**: Python 3.12+ Official Documentation (`asyncio` — *TaskGroups, Runners and Developing with Asyncio*); PEP 3156; Smith (2018), *Notes on Structured Concurrency*.

