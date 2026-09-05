---
type: comparison
domain: backend-systems
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: intermediate
tags:
  - backend
  - databases
  - comparison
  - sqlite
  - postgresql
  - persistence
prerequisites:
  - "[[SQLite WAL Mode and Concurrency]]"
  - "[[Database Isolation Levels and Phantom Reads in SQLite and Postgres]]"
related:
  - "[[Database Crash Consistency and Recovery]]"
  - "[[JARVIS State Store and Persistence]]"
used_by:
  - "[[JARVIS Component Architecture]]"
failure_modes:
  - "[[Lesson - SQLite Lock Starvation from Unclosed Readers]]"
implementation:
  - "[[JARVIS State Store and Persistence]]"
sources:
  - title: SQLite Appropriate Uses - When to Use SQLite vs Client/Server RDBMS
    type: PRIMARY_SOURCE
    url: https://www.sqlite.org/whentouse.html
---

# âš–ï¸ Comparison: SQLite WAL vs Client-Server PostgreSQL

## 1. Tabela Comparativa de Motores de Persistência

| Dimensão | SQLite em Modo WAL | PostgreSQL Cliente-Servidor |
|---|---|---|
| **Arquitetura de Processo** | Embebido no processo da aplicação (In-Process) | Processo daemon separado com conexões TCP/Unix Socket |
| **Latência de Leitura/Escrita** | **Microssegundos ($< 10\mu\text{s}$ - sem IPC/rede)** | Milissegundos ($0.5 - 2\text{ms}$ por overhead de rede) |
| **Concorrência de Escrita** | **Escritor único global** (Múltiplos leitores paralelos) | **Múltiplos escritores concorrentes por linha (MVCC)** |
| **Complexidade Operacional** | Zero (Arquivo único `.db`, sem portas nem senhas) | Média/Alta (Configuração de conexões, backups, pg_hba) |
| **Capacidade de Dados Recomendada**| Até centenas de GBs em disco local | Terabytes a Petabytes com particionamento distribuído |

---

## 2. Decisão de Engenharia para o JARVIS

### When should JARVIS choose SQLite WAL?
- Para estado local de agente, persistência de missões desktop e checkpoints de execução rápida em máquina única com latência ultrabaixa.

### When should JARVIS choose PostgreSQL?
- Para aplicações multi-tenant na nuvem com centenas de usuários escrevendo concorrentemente na mesma tabela.

### What failure mode does each introduce?
- **SQLite WAL**: Se múltiplos threads tentarem escrever concorrentemente sob carga pesada, ocorrem erros `database is locked` se o `busy_timeout` expirar.
- **PostgreSQL**: Falhas de conexão de rede, estouro de conexões no pool e sobrecarga de CPU por conexões ociosas.

---

## 3. Related Concepts
- [[SQLite WAL Mode and Concurrency]]
- [[Database Isolation Levels and Phantom Reads in SQLite and Postgres]]
- [[How to Diagnose and Resolve SQLite Database Locked Errors]]

