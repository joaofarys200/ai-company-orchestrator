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

# 🛠️ï¸ Runbook - How to Recover from Corrupted SQLite Databases

## 1. Critérios de Sucesso e Falha
- **Critério de Sucesso**: `PRAGMA integrity_check;` retorna `ok`, todos os registos recuperáveis da tabela `missions` e `steps` são restaurados num novo banco e o backend reinicia sem erros.
- **Critério de Falha**: O comando `.recover` falha ou o cabeçalho do arquivo está totalmente zerado sem backup.

---

## 2. Diagnóstico Inicial
Executar no terminal de administração:

```bash
sqlite3 database.db "PRAGMA quick_check;"
sqlite3 database.db "PRAGMA integrity_check;"
```

Se a saída apresentar erros como `*** in database main *** Page N is never used` ou `malformed`, o banco sofreu corrupção de páginas.

---

## 3. Procedimento de Recuperação Passo a Passo

### Passo 1: Isolar o Banco e Criar Backup dos Binários
```bash
cp database.db database.db.corrupted
cp database.db-wal database.db-wal.corrupted 2>/dev/null || true
```

### Passo 2: Executar Dump de Recuperação com Utilitário Nativo
```bash
sqlite3 database.db.corrupted ".recover" > recovered_data.sql
```

### Passo 3: Reconstruir Nova Base Limpa
```bash
# Remover arquivo corrompido
rm -f database.db database.db-wal database.db-shm

# Importar dados no novo banco
sqlite3 database.db < recovered_data.sql

# Reaplicar pragmas de produção
sqlite3 database.db "PRAGMA journal_mode = WAL;"
sqlite3 database.db "PRAGMA synchronous = NORMAL;"
sqlite3 database.db "PRAGMA busy_timeout = 15000;"
```

### Passo 4: Validação de Integridade Pós-Restauração
```bash
sqlite3 database.db "PRAGMA integrity_check;"
```

---

## 4. Related Concepts
- [[Database Crash Consistency and Recovery]]
- [[SQLite WAL Mode and Concurrency]]
- [[How to Diagnose and Resolve SQLite Database Locked Errors]]

