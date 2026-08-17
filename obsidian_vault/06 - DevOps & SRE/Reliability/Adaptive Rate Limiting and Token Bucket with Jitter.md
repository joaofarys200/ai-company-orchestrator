---
type: concept
domain: devops
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - devops
  - reliability
  - rate-limiting
  - token-bucket
  - jitter
  - backoff
prerequisites:
  - "[[Healthchecks and Circuit Breakers]]"
related:
  - "[[Model Routing and Fallback Strategies]]"
  - "[[SLI-SLO Metrics and Error Budgets]]"
used_by:
  - "[[JARVIS Model Harness Implementation]]"
failure_modes:
  - "[[Lesson - Unhandled Rate Limits and Context Explosion]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Exponential Backoff And Jitter (AWS Architecture Blog - Marc Brooker)
    type: PRIMARY_SOURCE
    url: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
  - title: RFC 6582 - The NewReno Modification to TCP's Fast Recovery Algorithm
    type: PRIMARY_SOURCE
    url: https://datatracker.ietf.org/doc/html/rfc6582
---

# ⏱️ Adaptive Rate Limiting and Token Bucket with Jitter

## 1. Pergunta Central
> *Como coordenar centenas de requisições concorrentes de agentes para provedores de LLM externos sem disparar erros HTTP 429 nem causar o problema de manada (*Thundering Herd*) quando o serviço se recupera?*

---

## 2. O Algoritmo do Balde de Tokens (Token Bucket)
O balde acumula tokens a uma taxa constante $R$ tokens/segundo até uma capacidade máxima $B$ (Burst Capacity). Cada requisição consome $k$ tokens (ex: contagem de tokens do prompt).

$$\text{Tokens Atuais}(t) = \min(B, \text{Tokens Anteriores} + (t - t_{\text{last}}) \times R)$$

---

## 3. Por que o Backoff Exponencial Ingênuo Falha (Thundering Herd)
Se 50 agentes falham simultaneamente e todos esperam exatamente $2^1 = 2\text{s}$, eles atacarão o servidor exatamente no segundo 2, causando novo 429.

**Full Jitter**: O tempo de espera é sorteado uniformemente entre 0 e o teto exponencial:

$$T_{\text{wait}} = \text{random\_uniform}(0, \min(T_{\text{max}}, T_{\text{base}} \times 2^{\text{attempt}}))$$

```python
import random
import time

def calculate_full_jitter_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
    temp_ceiling = min(max_delay, base_delay * (2 ** attempt))
    return random.uniform(0.0, temp_ceiling)
```

---

## 4. Related Concepts
- [[Healthchecks and Circuit Breakers]]
- [[Model Routing and Fallback Strategies]]
- [[Lesson - Unhandled Rate Limits and Context Explosion]]
