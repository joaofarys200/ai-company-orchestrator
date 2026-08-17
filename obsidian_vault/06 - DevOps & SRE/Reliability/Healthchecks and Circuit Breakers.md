---
type: pattern
domain: devops
difficulty: intermediate
tags:
  - devops
  - resilience
  - circuit-breaker
  - healthchecks
  - reliability
status: verified
---

# 🛡️ Healthchecks and Circuit Breakers

## 1. O Problema das Falhas em Cascata (Cascading Failures)
Se uma API externa de LLM ou base de dados começar a responder com latência de 30 segundos ou falhas `503`, os clientes que continuam a bombardear o serviço saturam as suas próprias threads de execução, consumindo memória e derrubando todo o ecossistema.

---

## 2. A Máquina de Estados do Circuit Breaker

```
               [ ESTADO: CLOSED ] (Operação Normal)
                      |
                      | (Falhas consecutivas >= Limiar, ex: 5)
                      v
               [ ESTADO: OPEN ] (Rejeita imediatamente sem chamar backend)
                      |
                      | (Após Recovery Timeout, ex: 30s)
                      v
             [ ESTADO: HALF-OPEN ] (Testa com 1 requisição canário)
             /                   \
(Sucesso do Canário)       (Falha do Canário)
           /                       \
          v                         v
   [ ESTADO: CLOSED ]        [ ESTADO: OPEN ]
```

---

## 3. Implementação Resiliente em Python

```python
import time
from enum import Enum
from typing import Callable, Any

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreakerOpenException(Exception):
    pass

class SimpleCircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        now = time.time()

        # 1. Se estiver OPEN, verificar se o tempo de recuperação já expirou
        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenException("Circuito ABERTO. Chamada externa bloqueada preventivamente.")

        try:
            result = await func(*args, **kwargs)
            # Se tiver sucesso em HALF_OPEN, fecha o circuito
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            return result
        except Exception as exc:
            self.failure_count += 1
            self.last_failure_time = now
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
            raise exc
```

---

## 4. Padrões de Healthchecks
- **Liveness Probe (`/healthz/liveness`)**: Verifica apenas se o processo Python está vivo e a responder a requisições básicas (se falhar, o orchestrator reinicia o container).
- **Readiness Probe (`/healthz/readiness`)**: Verifica se as dependências essenciais (banco de dados SQLite desbloqueado, disco com espaço, modelos locais carregados) estão prontas para receber tráfego de missões.

---

## 5. Related Concepts
- [[SLI-SLO Metrics and Error Budgets]]
- [[Model Routing and Fallback Strategies]]
- [[How to Implement Circuit Breakers for Flaky External APIs]]

---

## 6. Sources
- *Michael T. Nygard - Release It!: Design and Deploy Production-Ready Software*
- *Martin Fowler - CircuitBreaker Pattern*: https://martinfowler.com/bliki/CircuitBreaker.html
