---
type: concept
domain: backend-systems
difficulty: advanced
tags:
  - backend
  - distributed-systems
  - concurrency
status: verified
---

# ðŸŒ Manual AvanÃ§ado de Engenharia de Sistemas DistribuÃ­dos & ConcorrÃªncia AssÃ­ncrona

## ðŸ“Œ 1. VisÃ£o Geral Arquitetural
Este manual de referÃªncia destina-se ao **JARVIS OS** para governar a conceÃ§Ã£o, implementaÃ§Ã£o e otimizaÃ§Ã£o de sistemas distribuÃ­dos de alta concorrÃªncia, tolerantes a falhas e desacoplados.

---

## ðŸ›ï¸ 2. PadrÃµes de ComunicaÃ§Ã£o & Arquitetura Event-Driven (EDA)

### 2.1. Pub/Sub AssÃ­ncrono e Event Sourcing
- **Pub/Sub (Publish-Subscribe)**: Em vez de invocar endpoints HTTP sÃ­ncronos (que criam acoplamento rÃ­gido e cascatas de falha), os serviÃ§os emitem **Eventos de DomÃ­nio imutÃ¡veis** para um barramento assÃ­ncrono em memÃ³ria (`AsyncEventBus`) ou Message Brokers (Kafka / RabbitMQ).
- **Estrutura de Evento CanÃ³nico**:
  ```python
  from dataclasses import dataclass, field
  from typing import Any
  import time

  @dataclass(frozen=True)
  class DomainEvent:
      topic: str
      payload: dict[str, Any]
      correlation_id: str
      producer: str
      timestamp: float = field(default_factory=time.time)
  ```

### 2.2. PadrÃ£o Transactional Outbox
Para garantir que mensagens nÃ£o sÃ£o perdidas quando ocorrem falhas de rede durante o processamento de uma transaÃ§Ã£o na base de dados:
1. A alteraÃ§Ã£o de estado e o registo do evento sÃ£o gravados na **mesma transaÃ§Ã£o relacional** (tabela `outbox_events`).
2. Um processo em background (*Outbox Processor*) lÃª os eventos nÃ£o enviados e publica-os no Message Broker com garantia *At-Least-Once Delivery*.

### 2.3. CQRS (Command Query Responsibility Segregation)
- **Escritas (Commands)**: Otimizadas para validaÃ§Ã£o de regras de negÃ³cio, consistÃªncia transacional e operaÃ§Ãµes atÃ³micas (ex: SQLite / PostgreSQL).
- **Leituras (Queries)**: Otimizadas para pesquisas rÃ¡pidas e agregaÃ§Ãµes sem bloqueio de tabelas principais (ex: Ã­ndices RAG, tabelas desnormalizadas em memÃ³ria).

---

## âš¡ 3. ConcorrÃªncia AvanÃ§ada em Python (`asyncio`)

### 3.1. GestÃ£o de Ciclo de Vida do Event Loop
- **ProibiÃ§Ã£o de Bloqueio da Main Thread**: FunÃ§Ãµes sÃ­ncronas bloqueantes (I/O de ficheiros grandes, chamadas HTTP sÃ­ncronas com `requests`, computaÃ§Ã£o pesada em CPU) NUNCA devem ser executadas diretamente na thread principal do `asyncio`.
- **Uso de Thread/Process Pools**:
  ```python
  import asyncio
  from concurrent.futures import ThreadPoolExecutor

  _executor = ThreadPoolExecutor(max_workers=8)

  async def execute_blocking_io(func, *args):
      loop = asyncio.get_running_loop()
      return await loop.run_in_executor(_executor, func, *args)
  ```

### 3.2. PadrÃ£o Cancellation Token & Graceful Shutdown
- Todas as tarefas assÃ­ncronas de longa duraÃ§Ã£o em background devem aceitar um `asyncio.Event` de cancelamento para interromper o processamento em caso de shutdown ou interrupÃ§Ã£o do utilizador (*Barge-in*).

---

## ðŸ›¡ï¸ 4. TolerÃ¢ncia a Falhas & ResiliÃªncia (Circuit Breaker & Retry Strategy)

### 4.1. Circuit Breaker State Machine
O padrÃ£o *Circuit Breaker* impede que o agente continue a tentar invocar um serviÃ§o de terceiros (ex: API da Cloud) que esteja temporariamente indisponÃ­vel:
- **Estado FECHADO (Normal)**: Pedidos passam normalmente. Contagem de erros mantida.
- **Estado ABERTO (Falhado)**: Se a taxa de erros exceder o limite (ex: 50% em 10 pedidos), o circuito abre e rejeita pedidos instantaneamente sem chamar o serviÃ§o.
- **Estado MEIO-ABERTO (Teste)**: ApÃ³s um tempo de arrefecimento (ex: 30s), permite 1 pedido de teste para verificar se o serviÃ§o recuperou.

### 4.2. Backoff Exponencial com Jitter
Ao efetuar retentativas de chamadas falhadas, utilizar sem exceÃ§Ã£o **Backoff Exponencial com Jitter AleatÃ³rio** para evitar o efeito de avalanche de pedidos simultÃ¢neos (*Thundering Herd Problem*):
$$\text{delay} = \min(\text{max\_delay}, \text{base\_delay} \times 2^{\text{attempt}}) + \text{uniform}(0, \text{jitter})$$

