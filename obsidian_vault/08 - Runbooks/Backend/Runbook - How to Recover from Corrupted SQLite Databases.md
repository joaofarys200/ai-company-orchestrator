---
type: runbook
domain: backend-systems
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - runbook
  - backend
  - sqlite
  - database-corruption
  - disaster-recovery
prerequisites:
  - "[[Database Crash Consistency and Recovery]]"
  - "[[SQLite WAL Mode and Concurrency]]"
related:
  - "[[How to Diagnose and Resolve SQLite Database Locked Errors]]"
  - "[[JARVIS State Store and Persistence]]"
used_by:
  - "[[JARVIS MissionRecoveryWatchdog and Crash Recovery]]"
failure_modes:
  - "[[Lesson - SQLite Lock Starvation from Unclosed Readers]]"
implementation:
  - "[[JARVIS State Store and Persistence]]"
sources:
  - title: SQLite How To Corrupt An SQLite Database File and Recovery Tools (.recover)
    type: PRIMARY_SOURCE
    url: https://www.sqlite.org/howtocorrupt.html
---

# ðŸ› ï¸ Runbook - How to Recover from Corrupted SQLite Databases

## 1. CritÃ©rios de Sucesso e Falha
- **CritÃ©rio de Sucesso**: `PRAGMA integrity_check;` retorna `ok`, todos os registos recuperÃ¡veis da tabela `missions` e `steps` sÃ£o restaurados num novo banco e o backend reinicia sem erros.
- **CritÃ©rio de Falha**: O comando `.recover` falha ou o cabeÃ§alho do arquivo estÃ¡ totalmente zerado sem backup.

---

## 2. DiagnÃ³stico Inicial
Executar no terminal de administraÃ§Ã£o:

```bash
sqlite3 database.db "PRAGMA quick_check;"
sqlite3 database.db "PRAGMA integrity_check;"
```

Se a saÃ­da apresentar erros como `*** in database main *** Page N is never used` ou `malformed`, o banco sofreu corrupÃ§Ã£o de pÃ¡ginas.

---

## 3. Procedimento de RecuperaÃ§Ã£o Passo a Passo

### Passo 1: Isolar o Banco e Criar Backup dos BinÃ¡rios
```bash
cp database.db database.db.corrupted
cp database.db-wal database.db-wal.corrupted 2>/dev/null || true
```

### Passo 2: Executar Dump de RecuperaÃ§Ã£o com UtilitÃ¡rio Nativo
```bash
sqlite3 database.db.corrupted ".recover" > recovered_data.sql
```

### Passo 3: Reconstruir Nova Base Limpa
```bash
# Remover arquivo corrompido
rm -f database.db database.db-wal database.db-shm

# Importar dados no novo banco
sqlite3 database.db < recovered_data.sql

# Reaplicar pragmas de produÃ§Ã£o
sqlite3 database.db "PRAGMA journal_mode = WAL;"
sqlite3 database.db "PRAGMA synchronous = NORMAL;"
sqlite3 database.db "PRAGMA busy_timeout = 15000;"
```

### Passo 4: ValidaÃ§Ã£o de Integridade PÃ³s-RestauraÃ§Ã£o
```bash
sqlite3 database.db "PRAGMA integrity_check;"
```

---

## 4. Related Concepts
- [[Database Crash Consistency and Recovery]]
- [[SQLite WAL Mode and Concurrency]]
- [[How to Diagnose and Resolve SQLite Database Locked Errors]]

