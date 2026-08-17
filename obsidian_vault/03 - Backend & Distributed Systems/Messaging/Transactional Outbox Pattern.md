---
type: pattern
domain: backend-systems
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: intermediate
tags:
  - backend
  - microservices
  - outbox-pattern
  - event-driven
  - idempotency
prerequisites:
  - "[[Idempotency in Software Systems]]"
  - "[[Database Crash Consistency and Recovery]]"
related:
  - "[[Message Queues and Event-Driven Architectures]]"
  - "[[Distributed Transactions and Saga Pattern]]"
  - "[[Consensus and Raft Protocol]]"
used_by:
  - "[[JARVIS State Store and Persistence]]"
failure_modes:
  - "[[Lesson - SQLite Lock Starvation from Unclosed Readers]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Microservices Patterns - Transactional Outbox (Chris Richardson)
    type: PRIMARY_SOURCE
    url: https://microservices.io/patterns/data/transactional-outbox.html
---

# 📦 Transactional Outbox Pattern

## 1. Pergunta Central
> *Como garantir que a alteração de estado no banco de dados e a publicação do respetivo evento na fila de mensagens ocorram de forma atómica e consistente, sem perda de eventos em caso de crash pós-commit?*

---

## 2. O Problema do Dual-Write
Se uma aplicação tenta executar:
1. `db.commit()` (Salva a missão no banco)
2. `message_queue.publish()` (Publica evento para agentes)

Se o processo sofrer um crash ou a rede cair entre o passo 1 e o passo 2, a base de dados terá o registo gravado, mas os agentes **nunca receberão o evento**.
Se invertermos a ordem (1. publish, 2. commit), a mensagem pode ser processada por um agente antes do commit falhar, gerando inconsistência grave.

---

## 3. A Solução: Tabela `outbox` na Mesma Transação ACID

```
[ Agente / Aplicação ]
          |
          v (ÚNICA TRANSAÇÃO ACID ATÓMICA)
+------------------------------------------------------------+
| 1. UPDATE missions SET status = 'COMPLETED'                |
| 2. INSERT INTO outbox_events (event_type, payload, status) |
+-----------------------------+------------------------------+
                              | (Commit Confirmado!)
                              v
                   [ Tabela SQLite/Postgres ]
                              |
                              | (Leitura Assíncrona via Polling ou CDC)
                              v
                  [ Message Relay / Publisher ]
                              |
                              v
                  [ RabbitMQ / Kafka / Redis Bus ]
```

---

## 4. Implementação em Python com SQLite

```python
import sqlite3
import json

def complete_mission_atomically(conn: sqlite3.Connection, mission_id: str, result_data: dict):
    with conn:
        cursor = conn.cursor()
        
        # 1. Atualizar entidade de negócio
        cursor.execute(
            "UPDATE missions SET status = 'COMPLETED' WHERE id = ?",
            (mission_id,)
        )
        
        # 2. Inserir evento na tabela outbox NA MESMA transação
        event_payload = json.dumps({"mission_id": mission_id, "result": result_data})
        cursor.execute(
            """
            INSERT INTO outbox_events (event_name, payload, status, created_at)
            VALUES (?, ?, 'PENDING', datetime('now'))
            """,
            ("MISSION_COMPLETED", event_payload)
        )
        # Ambas as operações são confirmadas juntas atomicamente
```

---

## 5. Related Concepts
- [[Message Queues and Event-Driven Architectures]]
- [[Idempotency in Software Systems]]
- [[Distributed Transactions and Saga Pattern]]
