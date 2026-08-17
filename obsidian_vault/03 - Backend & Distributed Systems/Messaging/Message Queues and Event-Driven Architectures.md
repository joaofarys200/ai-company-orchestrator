---
type: concept
domain: backend-systems
difficulty: intermediate
tags:
  - backend
  - event-driven
  - message-queues
  - pub-sub
  - async
status: verified
---

# 📬 Message Queues and Event-Driven Architectures

## 1. Definição & Acoplamento Temporal
Em arquiteturas acopladas sincronicamente (chamadas HTTP diretas entre serviços ou agentes), a indisponibilidade ou lentidão temporária do receptor bloqueia o remetente.

Uma **Arquitetura Orientada a Eventos (EDA)** com **Filas de Mensagens (Message Queues)** introduz desacoplamento temporal e espacial:
- O produtor publica o evento e continua imediatamente a sua execução.
- Os consumidores processam mensagens ao seu próprio ritmo (*backpressure*), garantindo que picos de carga não derrubem os nós de processamento.

```
+-------------------+                                  +-------------------+
|  Producer Agent   |                                  |  Consumer Agent   |
|     (Devon)       |                                  |      (Quinn)      |
+---------+---------+                                  +---------+---------+
          |                                                      ^
          | 1. Publish("CODE_PATCHED")                           | 3. Consume
          v                                                      |
+----------------------------------------------------------------+--+
|                   EVENT BUS / MESSAGE QUEUE                       |
|   [ Msg 1: BUILD ] -> [ Msg 2: CODE_PATCHED ] -> [ Msg 3: TEST ]  |
+-------------------------------------------------------------------+
```

---

## 2. Padrões Fundamentais

### 2.1. Ponto-a-Ponto (Point-to-Point Queue)
- Cada mensagem na fila é consumida por **exatamente um worker**. Usado para distribuição de carga de compilação ou execução de testes de sandbox.

### 2.2. Publicação-Subscrição (Pub/Sub Topic)
- Cada evento publicado é entregue a **todos os subscritores** interessados (ex: telemetria de interface, persistência de logs e notificação sonora).

---

## 3. Implementação de Event Bus Assíncrono em Memória (Python)

```python
import asyncio
from typing import Callable, Dict, List, Any

class AsyncEventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def publish(self, event_type: str, payload: Dict[str, Any]):
        handlers = self._subscribers.get(event_type, [])
        tasks = []
        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                tasks.append(asyncio.create_task(handler(payload)))
            else:
                handler(payload)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
```

---

## 4. Related Concepts
- [[FastAPI and WebSocket Lifecycle Management]]
- [[Distributed Transactions and Saga Pattern]]
- [[How to Recover Interrupted Background Workers]]

---

## 5. Sources
- *Enterprise Integration Patterns (Hohpe & Woolf)*: https://www.enterpriseintegrationpatterns.com/
- *Martin Fowler - What do you mean by "Event-Driven"?*: https://martinfowler.com/articles/201701-event-driven.html
