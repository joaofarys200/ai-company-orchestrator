---
type: comparison
domain: backend-systems
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - backend
  - distributed-systems
  - messaging
  - delivery-semantics
  - idempotency
prerequisites:
  - "[[Message Queues and Event-Driven Architectures]]"
  - "[[Idempotency in Software Systems]]"
related:
  - "[[Transactional Outbox Pattern]]"
  - "[[Distributed Transactions and Saga Pattern]]"
  - "[[Engenharia_de_Sistemas_Distribuidos_e_Concorrencia]]"
used_by:
  - "[[JARVIS Component Architecture]]"
failure_modes:
  - "[[Lesson - SQLite Lock Starvation from Unclosed Readers]]"
implementation:
  - "[[JARVIS State Store and Persistence]]"
sources:
  - title: Designing Data-Intensive Applications (Kleppmann, Chapter 11 - Stream Processing)
    type: PRIMARY_SOURCE
    url: https://dataintensive.net/
---

# ⚖️ Exactly-Once vs At-Least-Once Delivery

## 1. Tabela Comparativa de Semânticas de Entrega

| Dimensão | At-Most-Once (No Máximo Uma Vez) | At-Least-Once (Pelo Menos Uma Vez) | Exactly-Once (Exatamente Uma Vez) |
|---|---|---|---|
| **Garantia Central** | Mensagens podem ser perdidas, mas nunca duplicadas | Nenhuma mensagem é perdida, mas duplicações podem ocorrer | Cada mensagem tem efeito final de processamento exatamente uma vez |
| **Comportamento sob Timeout** | Não retenta o envio | Retenta até receber confirmação positiva (ACK) | Retenta o envio + Desduplica no consumidor ou transação |
| **Sobrecarga de Rede** | Mínima (Fire-and-forget) | Moderada (Retentativas e ACKs) | Alta (Requer Chaves de Idempotência e Two-Phase Commit) |
| **Complexidade no Consumidor** | Nenhuma | Alta (Consumidor deve ser **100% Idempotente**) | Muito Alta (Coordenação de estado distribuído) |
| **Adoção na Indústria** | Logs de métricas e telemetria volátil | Padrão dominante de mensageria (Kafka, SQS, RabbitMQ) | Simulado via At-Least-Once + Idempotência |

---

## 2. A Verdade Teórica sobre "Exactly-Once"
Em redes IP com atrasos arbitrários e perda de pacotes (*Dois Generais Problem*), é matematicamente impossível garantir entrega física única de um pacote.

O que a indústria chama de "Exactly-Once Processing" é, na realidade:

$$\text{Exactly-Once Processing} = \text{At-Least-Once Delivery} + \text{Idempotent Consumer Deduplication}$$

---

## 3. Padrão de Desduplicação no Consumidor

```python
import sqlite3

def process_event_idempotently(db_conn: sqlite3.Connection, event_id: str, payload: dict):
    with db_conn:
        cursor = db_conn.cursor()
        
        # 1. Tentar registar o event_id na tabela de deduplicação
        cursor.execute(
            "INSERT OR IGNORE INTO processed_events (event_id, processed_at) VALUES (?, datetime('now'))",
            (event_id,)
        )
        
        # Se rowcount == 0, significa que o evento já foi processado anteriormente!
        if cursor.rowcount == 0:
            print(f"[Mensageria] Evento duplicado ignorado: {event_id}")
            return
            
        # 2. Executar o processamento de negócio
        apply_event_payload(cursor, payload)
```

---

## 4. Related Concepts
- [[Idempotency in Software Systems]]
- [[Transactional Outbox Pattern]]
- [[Distributed Transactions and Saga Pattern]]
