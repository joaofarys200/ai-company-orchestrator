---
type: lesson
domain: jarvis
source: production
severity: high
component: persistence
status: verified
source_type: JARVIS_INTERNAL
confidence: high
tags:
  - jarvis
  - lesson
  - persistence
  - sqlite
  - lock-starvation
prerequisites:
  - "[[SQLite WAL Mode and Concurrency]]"
related:
  - "[[Optimistic vs Pessimistic Locking]]"
  - "[[How to Diagnose and Resolve SQLite Database Locked Errors]]"
used_by:
  - "[[JARVIS State Store and Persistence]]"
failure_modes:
  - "[[Database Crash Consistency and Recovery]]"
implementation:
  - "[[JARVIS System Architecture]]"
sources:
  - title: JARVIS Incident Report - Incident INC-2026-08-05
    type: JARVIS_INTERNAL
    url: internal://incidents/INC-2026-08-05
---

# 📝 Lesson - SQLite Lock Starvation from Unclosed Readers

## 1. Failure
O servidor backend do JARVIS OS travou completamente durante o salvamento de um checkpoint de missão, emitindo sucessivos `sqlite3.OperationalError: database is locked`. O ficheiro `database.db-wal` cresceu para mais de 350MB e todas as operações de escrita falharam permanentemente até o processo ser reiniciado à força.

---

## 2. Root Cause
1. **Cursor de Leitura Não Fechado num Endpoint Assíncrono**: Um endpoint de telemetria executou `cursor = conn.cursor(); cursor.execute(...)` sem ler todos os resultados e sem invocar `cursor.close()` ou utilizar context manager `with conn:`.
2. **Impedimento de Checkpoint no WAL**: O SQLite em modo WAL permite múltiplos leitores concorrentes, mas **não consegue truncar o ficheiro WAL (checkpoint passivo)** enquanto existir uma transação de leitura ativa apontando para uma página antiga do log.
3. **Esgotamento de Busy Timeout**: Quando o escritor tentou sincronizar o checkpoint, a espera ultrapassou os 5 segundos e lançou exceção de lock.

---

## 3. Why Existing Protection Failed
O pragma `PRAGMA busy_timeout = 5000;` foi configurado com valor insuficiente (5s) e as conexões de leitura não estavam encapsuladas em blocos `try ... finally` ou context managers estritos.

---

## 4. Corrective Action
1. **Ajuste de Pragmas Globais**:
   - `PRAGMA busy_timeout = 15000;` (15 segundos de tolerância).
   - `PRAGMA wal_autocheckpoint = 1000;` com checkpoint ativo periódico via background task.
2. **Enforce de Context Managers**: Toda a função de persistência em [`database.py`](file:///c:/Users/joaor/Desktop/JarvisOS/database.py) foi refatorada para utilizar estritamente `with sqlite3.connect(...) as conn:` garantindo que o fecho do cursor e o commit/rollback ocorram mesmo sob exceções.

---

## 5. Generalizable Principle
> *Em SQLite WAL, um leitor esquecido aberto é tão destrutivo para a escrita quanto um bloqueio de tabela em bancos tradicionais.*

---

## 6. Related Concepts
- [[SQLite WAL Mode and Concurrency]]
- [[How to Diagnose and Resolve SQLite Database Locked Errors]]
- [[JARVIS State Store and Persistence]]
- [[Database Crash Consistency and Recovery]]

---

## 7. Tests Added
- `tests/test_database_concurrency.py::test_concurrent_readers_do_not_block_wal_checkpoint`
- `tests/test_database_concurrency.py::test_unclosed_cursor_leak_detection`
