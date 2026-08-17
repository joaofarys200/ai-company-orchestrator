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

## 1. Tabela Comparativa de Motores de PersistÃªncia

| DimensÃ£o | SQLite em Modo WAL | PostgreSQL Cliente-Servidor |
|---|---|---|
| **Arquitetura de Processo** | Embebido no processo da aplicaÃ§Ã£o (In-Process) | Processo daemon separado com conexÃµes TCP/Unix Socket |
| **LatÃªncia de Leitura/Escrita** | **Microssegundos ($< 10\mu\text{s}$ - sem IPC/rede)** | Milissegundos ($0.5 - 2\text{ms}$ por overhead de rede) |
| **ConcorrÃªncia de Escrita** | **Escritor Ãºnico global** (MÃºltiplos leitores paralelos) | **MÃºltiplos escritores concorrentes por linha (MVCC)** |
| **Complexidade Operacional** | Zero (Arquivo Ãºnico `.db`, sem portas nem senhas) | MÃ©dia/Alta (ConfiguraÃ§Ã£o de conexÃµes, backups, pg_hba) |
| **Capacidade de Dados Recomendada**| AtÃ© centenas de GBs em disco local | Terabytes a Petabytes com particionamento distribuÃ­do |

---

## 2. DecisÃ£o de Engenharia para o JARVIS

### When should JARVIS choose SQLite WAL?
- Para estado local de agente, persistÃªncia de missÃµes desktop e checkpoints de execuÃ§Ã£o rÃ¡pida em mÃ¡quina Ãºnica com latÃªncia ultrabaixa.

### When should JARVIS choose PostgreSQL?
- Para aplicaÃ§Ãµes multi-tenant na nuvem com centenas de usuÃ¡rios escrevendo concorrentemente na mesma tabela.

### What failure mode does each introduce?
- **SQLite WAL**: Se mÃºltiplos threads tentarem escrever concorrentemente sob carga pesada, ocorrem erros `database is locked` se o `busy_timeout` expirar.
- **PostgreSQL**: Falhas de conexÃ£o de rede, estouro de conexÃµes no pool e sobrecarga de CPU por conexÃµes ociosas.

---

## 3. Related Concepts
- [[SQLite WAL Mode and Concurrency]]
- [[Database Isolation Levels and Phantom Reads in SQLite and Postgres]]
- [[How to Diagnose and Resolve SQLite Database Locked Errors]]

