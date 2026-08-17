---
type: comparison
domain: backend-systems
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - backend
  - distributed-systems
  - comparison
  - saga
  - transactional-outbox
  - messaging
prerequisites:
  - "[[Transactional Outbox Pattern]]"
  - "[[Distributed Transactions and Saga Pattern]]"
related:
  - "[[Exactly-Once vs At-Least-Once Delivery]]"
  - "[[Message Queues and Event-Driven Architectures]]"
used_by:
  - "[[JARVIS Component Architecture]]"
failure_modes:
  - "[[Database Crash Consistency and Recovery]]"
implementation:
  - "[[JARVIS State Store and Persistence]]"
sources:
  - title: Microservices Patterns - Transaction Management (Chris Richardson)
    type: PRIMARY_SOURCE
    url: https://microservices.io/patterns/data/saga.html
---

# ⚖️ Comparison: Saga Pattern vs Transactional Outbox

## 1. Tabela Comparativa de Padrões de Consistência

| Dimensão | Transactional Outbox Pattern | Saga Pattern (Orquestrado / Coreografado) |
|---|---|---|
| **Problema que Resolve** | Dual-write atómico entre Banco Local e Fila de Mensagens | Consistência eventual entre múltiplos microserviços independentes |
| **Mecanismo Central** | Tabela `outbox` na mesma transação ACID do estado de negócio | Sequência de transações locais com **Transações de Compensação** |
| **Complexidade de Rollback** | Simples (Rollback padrão do banco de dados aborta a mensagem) | Complexa (Requer lógica explícita para desfazer passos passados) |
| **Isolamento de Dados** | Snapshot Isolation no banco local | Sem isolamento global (Anomalias de leitura suja entre sagas) |

---

## 2. Decisão de Engenharia para o JARVIS

### When should JARVIS choose Transactional Outbox?
- Ao disparar eventos de missão ou telemetria para filas e WebSockets mantendo garantia estrita de que o evento só é emitido se o estado for persistido no SQLite.

### When should JARVIS choose Saga Pattern?
- Ao orquestrar fluxos de negócio distribuídos com serviços externos (ex: criar repositório no GitHub $\rightarrow$ provisionar DNS $\rightarrow$ emitir fatura no Stripe).

### What failure mode does each introduce?
- **Transactional Outbox**: Mensagens acumulando na tabela `outbox` se o worker de despacho travar.
- **Saga Pattern**: Falha em cascata de transações de compensação deixando dados em estado inconsistente (*Pivot Step Failure*).

---

## 3. Related Concepts
- [[Transactional Outbox Pattern]]
- [[Distributed Transactions and Saga Pattern]]
- [[Exactly-Once vs At-Least-Once Delivery]]
