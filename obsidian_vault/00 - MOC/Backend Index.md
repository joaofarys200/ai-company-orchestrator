---
type: index
domain: backend-systems
difficulty: intermediate
tags:
  - backend
  - databases
  - persistence
  - sqlite
  - postgresql
  - distributed-systems
  - consensus
  - raft
  - sharding
  - moc
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
---

# ⚙️ Backend & Distributed Systems Index

Este MOC organiza o conhecimento sobre persistência, motores de dados, controle de concorrência, protocolos em tempo real, mensageria, consenso Raft e particionamento horizontal.

---

## 🗄️ Persistence & Storage Engines
- [[SQLite WAL Mode and Concurrency]] — Write-Ahead Logging, leitores não-bloqueantes e checkpoints.
- [[Database Isolation Levels and Phantom Reads in SQLite and Postgres]] — Fenômenos ANSI SQL e Snapshot Isolation no WAL.
- [[Comparison - SQLite WAL vs Client-Server PostgreSQL]] — Comparativo entre banco in-process e servidor cliente-servidor.
- [[Database Crash Consistency and Recovery]] — Propriedades ACID, chamadas `fsync` e integridade pós-falha.
- [[Tratado_Completo_de_Engenharia_de_Sistemas_Distribuidos_e_Bases_de_Dados]] — Monografia sobre motores de armazenamento e replicação.

## 🔒 Concurrency & Locking
- [[Optimistic vs Pessimistic Locking]] — Estratégias de controle de concorrência e resolução de colisões de escrita.
- [[Distributed Locks and Fencing Tokens]] — Prevenção do lease expiration bug com barreiras monotónicas.
- [[Engenharia_de_Sistemas_Distribuidos_e_Concorrencia]] — Monografia sobre modelos de consistência e multithreading.

## 🌐 WebSockets & Real-time Streaming
- [[FastAPI and WebSocket Lifecycle Management]] — Túneis persistentes, heartbeats, reconexão e broadcast.
- [[Comparison - REST Polling vs WebSocket Full-Duplex Streaming]] — Comparativo de overhead de protocolo e latência.

## 📬 Messaging & Event Architectures
- [[Transactional Outbox Pattern]] — Eliminação do problema de dual-write entre banco e fila.
- [[Comparison - Saga Pattern vs Transactional Outbox]] — Comparativo entre consistência multi-serviço e outbox local.
- [[Exactly-Once vs At-Least-Once Delivery]] — Semânticas de entrega e desduplicação no consumidor.
- [[Message Queues and Event-Driven Architectures]] — Desacoplamento temporal, pub/sub e buffers de tarefas.

## 🌐 Distributed Systems, Consensus & Sharding
- [[Consensus and Raft Protocol]] — Eleição de líderes e replicação de logs baseada em quorum majoritário.
- [[Raft Joint Consensus and Dynamic Membership Changes]] — Transição segura de configurações de cluster via consensos conjuntos.
- [[Database Sharding and Consistent Hashing Rings]] — Particionamento horizontal de dados e anéis de hash consistentes.
- [[Eventual Consistency and CRDTs]] — Estruturas de dados replicadas livres de conflito (CvRDT e CmRDT).
- [[Distributed Transactions and Saga Pattern]] — Orquestração e compensação de transações distribuídas.
- [[DDIA_Designing_Data_Intensive_Applications_BOK]] — Monografia sobre sistemas intensivos em dados (Kleppmann).

---

## 🛠️ Runbooks Relacionados em 08 - Runbooks/Backend
- [[How to Diagnose and Resolve SQLite Database Locked Errors]] — Resolução de timeouts de lock no banco de dados.
- [[Runbook - How to Recover from Corrupted SQLite Databases]] — Restauração de banco corrompido com utilitário `.recover`.
- [[Runbook - How to Resolve Stale Distributed Locks and Fencing Collisions]] — Resolução de locks obsoletos e colisões de fencing.
- [[How to Recover Interrupted Background Workers]] — Checkpointing e recuperação de tarefas inacabadas.

## 📝 Lições de Produção em 09 - JARVIS/Lessons
- [[Lesson - SQLite Lock Starvation from Unclosed Readers]] — Travamento de banco causado por cursores não finalizados.
