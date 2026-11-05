---
type: concept
domain: backend-systems
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - backend
  - distributed-systems
  - backpressure
  - load-shedding
  - queueing-theory
  - reliability
---

# 🌊 Backpressure, Load Shedding and Little's Law in Async Pipelines

## 1. Fundamentos de Teoria de Filas em Sistemas Assíncronos
Filas ilimitadas (`asyncio.Queue()` sem `maxsize`) não absorvem sobrecarga sustentada — apenas convertem excesso de tráfego em **esgotamento de RAM (OOM)** e latência infinita. Duas leis matemáticas governam qualquer pipeline assíncrono:

1. **Lei de Little** (estacionária para qualquer distribuição):
   $$L = \lambda \cdot W$$
   onde $L$ é a concorrência média em voo, $\lambda$ a taxa de chegada (req/s) e $W$ o tempo médio de resposta. Se um LLM externo abranda de $W = 2\text{ s}$ para $W = 20\text{ s}$ sob o mesmo $\lambda$, a memória e sockets retidos ($L$) multiplicam-se por $10\times$.
2. **Aproximação de Kingman (Explosão Não-Linear perto de $\rho \to 1$)**:
   $$E[W_q] \approx \left(\frac{\rho}{1 - \rho}\right) \left(\frac{c_a^2 + c_s^2}{2}\right) \tau$$
   Quando a utilização $\rho = \lambda / \mu$ ultrapassa $80\%\text{–}85\%$ sob variância alta ($c_s^2 \gg 1$, comum em inferência LLM), o tempo em fila $E[W_q]$ tende assintoticamente para infinito.

---

## 2. Mecanismos de Defesa: Backpressure vs Load Shedding

| Mecanismo | Quando Aplicar | Ação Técnica |
|---|---|---|
| **Backpressure (Controlo de Fluxo)** | Produtor cooperativo controlável (workers internos, streams, batch jobs) | `asyncio.Queue(maxsize=K)`, créditos de janela, bloqueio no `await queue.put()` |
| **Load Shedding (Descarte Seletivo)** | Tráfego externo interativo acima da capacidade máxima $\mu$ | Rejeitar imediatamente (`HTTP 429/503`) pedidos de baixa prioridade antes de alocar CPU/DB |
| **LIFO + Timeout Deadline** | Picos súbitos onde clientes já desistiram de pedidos antigos | Servir pedidos mais recentes (*Last-In, First-Out*) e descartar itens cujo `deadline` expirou na fila |

---

## 3. Implementação de Referência (Fila com Deadline & Shedding)

```python
import asyncio
import time

class BoundedDeadlineQueue:
    def __init__(self, maxsize: int = 64) -> None:
        self._q: asyncio.Queue[tuple[float, object]] = asyncio.Queue(maxsize=maxsize)

    def try_enqueue(self, payload: object, ttl_sec: float = 15.0) -> bool:
        if self._q.full():
            return False  # Load shedding imediato O(1)
        self._q.put_nowait((time.monotonic() + ttl_sec, payload))
        return True

    async def dequeue_fresh(self) -> object:
        while True:
            deadline, payload = await self._q.get()
            if time.monotonic() <= deadline:
                return payload  # Descarta trabalho já expirado na fila
```

---

## 4. Conceitos Relacionados & Fontes
- [[Adaptive Rate Limiting and Token Bucket with Jitter]]
- [[Healthchecks and Circuit Breakers]]
- [[Message Queues and Event-Driven Architectures]]
- [[Python Asyncio Event Loop Internals, Backpressure and Thread Offloading]]
- [[Tail Latency Engineering - P99 Amplification, Hedged Requests and GC Pauses]]
- **Fontes**: Little (1961), *A Proof for the Queuing Formula: $L = \lambda W$*; AWS Builders' Library, *Using Load Shedding to Avoid Overload*; Nichols & Jacobson (2012), *Controlling Queue Delay (CoDel)* (ACM Queue).

