---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
difficulty: advanced
tags:
  - jarvis
  - database
  - sqlite
  - wal
  - checkpointing
  - pragma
prerequisites:
  - "[[SQLite WAL Mode and Concurrency]]"
  - "[[Database Crash Consistency and Recovery]]"
related:
  - "[[JARVIS MissionStateStore and Persistence Engine]]"
  - "[[How to Diagnose and Resolve SQLite Database Locked Errors]]"
used_by:
  - "[[JARVIS State Store and Persistence]]"
failure_modes:
  - "[[Lesson - SQLite Lock Starvation from Unclosed Readers]]"
implementation:
  - "[[JARVIS State Store and Persistence]]"
sources:
  - title: JARVIS Codebase - database.py and SQLite pragmas
    type: JARVIS_INTERNAL
    url: internal://database.py
---

# ðŸ—„ï¸ JARVIS SQLite WAL Checkpoint Daemon and PRAGMA Tuning

## 1. Purpose
O subsistema de persistÃªncia e sintonia de PRAGMAs em `database.py` governa a saÃºde, concorrÃªncia e integridade a longo prazo da base SQLite do JARVIS OS, garantindo que leituras e escritas concorrentes ocorram sem travamentos e que o arquivo WAL seja truncado periodicamente.

---

## 2. ConfiguraÃ§Ã£o de PRAGMAs de ProduÃ§Ã£o
Ao inicializar cada conexÃ£o no pool de banco de dados, o JARVIS aplica rigorosamente:

```sql
PRAGMA journal_mode = WAL;         -- Habilita Write-Ahead Logging para concorrÃªncia leitor-escritor
PRAGMA synchronous = NORMAL;       -- BalanÃ§o Ã³timo entre performance e durabilidade em WAL mode
PRAGMA busy_timeout = 15000;       -- Aguarda atÃ© 15 segundos antes de lanÃ§ar 'database is locked'
PRAGMA temp_store = MEMORY;        -- Tabelas temporÃ¡rias e Ã­ndices armazenados em RAM
PRAGMA foreign_keys = ON;          -- Integridade referencial obrigatÃ³ria entre tabelas
PRAGMA cache_size = -64000;        -- Aloca 64 MB de cache de pÃ¡ginas em memÃ³ria
PRAGMA wal_autocheckpoint = 1000;  -- Executa checkpoint passivo a cada 1000 pÃ¡ginas escritas
```

---

## 3. EstratÃ©gia de Checkpointing
- **Passivo (AutomÃ¡tico)**: Disparado pelo SQLite quando o arquivo WAL atinge 1000 pÃ¡ginas.
- **Ativo (Truncate PeriÃ³dico)**: Durante perÃ­odos de ociosidade, o watchdog executa `PRAGMA wal_checkpoint(TRUNCATE);` para reiniciar o arquivo WAL em tamanho zero.

---

## 4. Dependencies
- [`database.py`](file:///c:/Users/joaor/Desktop/JarvisOS/database.py)

---

## 5. Failure Modes & Recovery
- **Failure**: Arquivo WAL crescendo indefinidamente devido a leitor zumbi (ver [[Lesson - SQLite Lock Starvation from Unclosed Readers]]).
- **Recovery**: O watchdog identifica a transaÃ§Ã£o antiga, encerra a conexÃ£o fantasma e forÃ§a o checkpoint truncate.

---

## 6. Related Concepts
- [[SQLite WAL Mode and Concurrency]]
- [[Database Crash Consistency and Recovery]]
- [[Runbook - How to Recover from Corrupted SQLite Databases]]

