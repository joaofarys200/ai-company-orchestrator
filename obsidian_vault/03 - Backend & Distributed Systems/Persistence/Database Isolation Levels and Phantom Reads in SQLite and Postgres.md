---
type: comparison
domain: backend-systems
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - backend
  - databases
  - isolation-levels
  - sqlite
  - acid
  - phantom-reads
prerequisites:
  - "[[SQLite WAL Mode and Concurrency]]"
  - "[[Optimistic vs Pessimistic Locking]]"
related:
  - "[[Database Crash Consistency and Recovery]]"
  - "[[Distributed Locks and Fencing Tokens]]"
used_by:
  - "[[JARVIS State Store and Persistence]]"
failure_modes:
  - "[[Lesson - SQLite Lock Starvation from Unclosed Readers]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: A Critique of ANSI SQL Isolation Levels (Berenson et al., SIGMOD 1995)
    type: PRIMARY_SOURCE
    url: https://arxiv.org/abs/cs/0701157
  - title: SQLite Transaction Isolation and WAL Mode Documentation
    type: PRIMARY_SOURCE
    url: https://www.sqlite.org/isolation.html
---

# ⚖️ Database Isolation Levels and Phantom Reads in SQLite and Postgres

## 1. Tabela de Fenômenos de Concorrência ANSI SQL vs MVCC

| Nível de Isolamento | Dirty Reads ($G_1$) | Non-Repeatable Reads ($G_{2a}$) | Phantom Reads ($A_3$) | Write Skew ($A_{5b}$) | Suporte no SQLite |
|---|---|---|---|---|---|
| **Read Uncommitted** | Possível | Possível | Possível | Possível | Sim (via `PRAGMA read_uncommitted`) |
| **Read Committed** | **Prevenido** | Possível | Possível | Possível | Não (promovido para Snapshot) |
| **Repeatable Read** | **Prevenido** | **Prevenido** | Possível (ANSI) / Prevenido (MVCC) | Possível | Não nativo |
| **Snapshot Isolation** | **Prevenido** | **Prevenido** | **Prevenido** | Possível | **Padrão no SQLite WAL Mode** |
| **Serializable** | **Prevenido** | **Prevenido** | **Prevenido** | **Prevenido** | Padrão no SQLite Rollback Journal |

---

## 2. Isolamento no SQLite WAL: Snapshot Isolation Real
Quando o SQLite opera em modo WAL:
1. Quando uma transação de leitura começa (`BEGIN`), ela adquire uma **visão instantânea e congelada (Snapshot)** do banco de dados correspondente ao último commit gravado no log WAL.
2. Escritores concorrentes podem gravar e commitar novas transações no WAL sem bloquear o leitor e sem introduzir *Dirty Reads* ou *Phantom Reads*.
3. O leitor enxerga consistentemente o banco no estado do instante de início da sua transação.

---

## 3. Related Concepts
- [[SQLite WAL Mode and Concurrency]]
- [[Optimistic vs Pessimistic Locking]]
- [[Database Crash Consistency and Recovery]]
- [[Lesson - SQLite Lock Starvation from Unclosed Readers]]
