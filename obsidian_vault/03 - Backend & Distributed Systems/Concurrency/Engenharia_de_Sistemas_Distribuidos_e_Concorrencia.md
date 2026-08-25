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

# 🌐 Manual Avançado de Engenharia de Sistemas Distribuídos & Concorrência Assíncrona

## 📌 1. Visão Geral Arquitetural
Este manual de referência destina-se ao **JARVIS OS** para governar a conceção, implementação e otimização de sistemas distribuídos de alta concorrência, tolerantes a falhas e desacoplados.

---

## 🏛️ 2. Padrões de Comunicação & Arquitetura Event-Driven (EDA)

### 2.1. Pub/Sub Assíncrono e Event Sourcing
- **Pub/Sub (Publish-Subscribe)**: Em vez de invocar endpoints HTTP síncronos (que criam acoplamento rígido e cascatas de falha), os serviços emitem **Eventos de Domínio imutáveis** para um barramento assíncrono em memória (`AsyncEventBus`) ou Message Brokers (Kafka / RabbitMQ).
- **Estrutura de Evento Canónico**:

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

### 2.2. Padrão Transactional Outbox
Para garantir que mensagens não são perdidas quando ocorrem falhas de rede durante o processamento de uma transação na base de dados:
1. A alteração de estado e o registo do evento são gravados na **mesma transação relacional** (tabela `outbox_events`).
2. Um processo em background (*Outbox Processor*) lê os eventos não enviados e publica-os no Message Broker com garantia *At-Least-Once Delivery*.

### 2.3. CQRS (Command Query Responsibility Segregation)
- **Escritas (Commands)**: Otimizadas para validação de regras de negócio, consistência transacional e operações atómicas (ex: SQLite / PostgreSQL).
- **Leituras (Queries)**: Otimizadas para pesquisas rápidas e agregações sem bloqueio de tabelas principais (ex: índices RAG, tabelas desnormalizadas em memória).

---

## ⚡ 3. Concorrência Avançada em Python (`asyncio`)

### 3.1. Gestão de Ciclo de Vida do Event Loop
- **Proibição de Bloqueio da Main Thread**: Funções síncronas bloqueantes (I/O de ficheiros grandes, chamadas HTTP síncronas com `requests`, computação pesada em CPU) NUNCA devem ser executadas diretamente na thread principal do `asyncio`.
- **Uso de Thread/Process Pools**:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=8)

async def execute_blocking_io(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, func, *args)
```

### 3.2. Padrão Cancellation Token & Graceful Shutdown
- Todas as tarefas assíncronas de longa duração em background devem aceitar um `asyncio.Event` de cancelamento para interromper o processamento em caso de shutdown ou interrupção do utilizador (*Barge-in*).

---

## 🛡️ 4. Tolerância a Falhas & Resiliência (Circuit Breaker & Retry Strategy)

### 4.1. Circuit Breaker State Machine
O padrão *Circuit Breaker* impede que o agente continue a tentar invocar um serviço de terceiros (ex: API da Cloud) que esteja temporariamente indisponível:
- **Estado FECHADO (Normal)**: Pedidos passam normalmente. Contagem de erros mantida.
- **Estado ABERTO (Falhado)**: Se a taxa de erros exceder o limite (ex: 50% em 10 pedidos), o circuito abre e rejeita pedidos instantaneamente sem chamar o serviço.
- **Estado MEIO-ABERTO (Teste)**: Após um tempo de arrefecimento (ex: 30s), permite 1 pedido de teste para verificar se o serviço recuperou.

### 4.2. Backoff Exponencial com Jitter
Ao efetuar retentativas de chamadas falhadas, utilizar sem exceção **Backoff Exponencial com Jitter Aleatório** para evitar o efeito de avalanche de pedidos simultâneos (*Thundering Herd Problem*):
$$\text{delay} = \min(\text{max\_delay}, \text{base\_delay} \times 2^{\text{attempt}}) + \text{uniform}(0, \text{jitter})$$
