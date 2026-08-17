---
type: troubleshooting
domain: devops
difficulty: intermediate
tags:
  - devops
  - troubleshooting
  - circuit-breaker
  - resilience
  - api-client
status: verified
---

# 🛠️ How to Implement Circuit Breakers for Flaky External APIs

## 1. Sintomas & Diagnóstico
- Chamadas a APIs externas de LLM ou serviços de terceiros começam a demorar >30 segundos ou devolvem erros `500/502/503/504`.
- As threads do servidor backend ficam presas aguardando respostas, esgotando o connection pool e derrubando a aplicação inteira.

---

## 2. Implementação Resiliente Passo a Passo (Python / Tenacity / Custom)

```python
import httpx
import asyncio
import time
from typing import Any, Dict

class CircuitBreakerOpenError(Exception):
    pass

class APICircuitBreaker:
    def __init__(self, failure_limit: int = 4, cooldown_sec: float = 20.0):
        self.failure_limit = failure_limit
        self.cooldown_sec = cooldown_sec
        self.state = "CLOSED"
        self.consecutive_failures = 0
        self.opened_at = 0.0

    async def execute_request(self, client: httpx.AsyncClient, url: str, json_data: dict) -> Dict[str, Any]:
        now = time.time()

        # 1. Verificar se o circuito está aberto
        if self.state == "OPEN":
            if now - self.opened_at > self.cooldown_sec:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError("Circuito Aberto: API externa instável.")

        try:
            # 2. Executar requisição com timeout estrito de 10s
            response = await client.post(url, json=json_data, timeout=10.0)
            
            # Tratar 5xx como falha de infraestrutura
            if response.status_code >= 500:
                raise httpx.HTTPStatusError("Server error", request=response.request, response=response)
                
            response.raise_for_status()
            
            # Se for bem-sucedido, resetar falhas e fechar circuito
            self.state = "CLOSED"
            self.consecutive_failures = 0
            return response.json()

        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.NetworkError) as err:
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.failure_limit:
                self.state = "OPEN"
                self.opened_at = time.time()
            raise err
```

---

## 3. Estratégia de Fallback Imediato
Quando o Circuit Breaker lança `CircuitBreakerOpenError`, a aplicação não deve propagar um erro `500` para o utilizador:
1. Recorrer ao modelo ou endpoint de contingência local ([[Model Routing and Fallback Strategies]]).
2. Ou devolver dados cacheados / resposta degradada segura.

---

## 4. Related Concepts
- [[Healthchecks and Circuit Breakers]]
- [[Model Harness Architecture]]
- [[Model Routing and Fallback Strategies]]

---

## 5. Sources
- *Netflix Hystrix Circuit Breaker Pattern Wiki*: https://github.com/Netflix/Hystrix/wiki/How-it-Works
- *Martin Fowler - CircuitBreaker*: https://martinfowler.com/bliki/CircuitBreaker.html
