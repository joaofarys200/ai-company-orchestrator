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
  - caching
  - cache-stampede
  - singleflight
  - xfetch
  - consistency
---

# ⚡ Cache Consistency Patterns, Stampede Mitigation and Probabilistic Early Expiration

## 1. Padrões de Coerência e Anomalias de Invalidação
No padrão **Cache-Aside** (o mais comum em aplicações), a aplicação lê primeiro da cache e, em *cache miss*, consulta a base de dados e popula a cache.

- **Corrida Clássica Read-Modify-Write**: Leitor $A$ sofre *miss* e lê `v1` do banco; Escritor $B$ grava `v2` no banco e invalida a cache; Leitor $A$ retoma e grava `v1` obsoleto na cache.
  - *Mitigação*: Usar `DELETE` (invalidação) em vez de `SET` no caminho de escrita, acoplar versão monotónica/CAS (*Compare-And-Swap*) ou TTL curto de segurança.

---

## 2. Cache Stampede (Thundering Herd) & Duas Defesas Complementares
Quando uma chave quente (*hot key*: índice de documentos, resposta RAG ou configuração global) expira exatamente num pico de concorrência, centenas de pedidos sofrem *cache miss* simultâneo e saturam a base de dados ou o LLM.

1. **Request Coalescing (`Singleflight`)**:
   - Apenas a **primeira** corrotina/thread que deteta o *miss* executa a computação custosa; todas as restantes subscrevem a mesma `Future` em voo, reduzindo $N$ chamadas idênticas a $1$.
2. **Expiração Antecipada Probabilística (Algoritmo XFetch — Vattani et al.)**:
   - Antes do `expiry` real, cada leitor decide probabilisticamente recomputar em background quando:
     $$t_{\text{now}} - \Delta \cdot \beta \cdot \ln(\text{rand}(0,1)) \ge t_{\text{expiry}}$$
     onde $\Delta$ é a duração da última recomputação e $\beta \ge 1.0$ controla a agressividade (como $\ln(u) < 0$, o termo $-\Delta\beta\ln(u)$ é positivo e cresce exponencialmente perto da expiração).

---

## 3. Implementação de Referência (Async Singleflight em Python)

```python
import asyncio
from typing import Awaitable, Callable, Dict, TypeVar

T = TypeVar("T")

class AsyncSingleflight:
    def __init__(self) -> None:
        self._inflight: Dict[str, asyncio.Future] = {}

    async def do(self, key: str, fn: Callable[[], Awaitable[T]]) -> T:
        if key in self._inflight:
            return await asyncio.shield(self._inflight[key])
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._inflight[key] = fut
        try:
            res = await fn()
            fut.set_result(res)
            return res
        except Exception as exc:
            fut.set_exception(exc)
            raise
        finally:
            self._inflight.pop(key, None)
```

---

## 4. Conceitos Relacionados & Fontes
- [[Semantic Caching for LLM Responses and Invalidation Strategies]]
- [[Optimistic vs Pessimistic Locking]]
- [[Lesson - Self-Improvement Cycle 3 - FINDING-01-RAG-LRU-CACHE]]
- [[Backpressure, Load Shedding and Little's Law in Async Pipelines]]
- **Fontes**: Vattani, Chierichetti & Lowenstein (2015), *Optimal Probabilistic Cache Stampede Prevention (XFetch)* (VLDB); Nishtala et al. (2013), *Scaling Memcache at Facebook* (USENIX NSDI).

