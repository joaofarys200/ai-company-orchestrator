---
type: concept
domain: backend-systems
difficulty: intermediate
tags:
  - backend
  - databases
  - sqlite
  - wal
  - concurrency
  - acid
status: verified
---

# 🗄️ SQLite WAL Mode and Concurrency

## 1. Definição & O Modo Tradicional Rollback Journal
Por padrão, o SQLite opera em modo *Rollback Journal*, onde qualquer operação de escrita adquire um bloqueio exclusivo (`EXCLUSIVE lock`) sobre todo o ficheiro do banco de dados, impedindo simultaneamente todas as leituras e outras escritas.

O **Write-Ahead Logging (WAL)** transforma radicalmente a mecânica de concorrência:
- **Leitores NUNCA bloqueiam Escritores**.
- **Escritores NUNCA bloqueiam Leitores**.
- Permite múltiplos leitores em paralelo concorrendo com exatamente um escritor ativo.

```
Modo Tradicional (Rollback Journal):
[ Leitor 1 ] ----+
[ Leitor 2 ] ----+---> [ DB File BLOQUEADO por 1 Escritor ] -> (Bloqueio Total)
[ Escritor ] ----+

Modo WAL (Write-Ahead Log):
[ Leitor 1 ] ---------> [ DB Principal (Snapshot Estável) ] (Sem Bloqueio)
[ Leitor 2 ] ---------> [ DB Principal + WAL Index (SHM)  ] (Sem Bloqueio)
[ Escritor ] ---------> [ Ficheiro .db-wal (Append-Only)   ] (Concorrente com Leitores!)
```

---

## 2. Estrutura de Ficheiros do Modo WAL
Quando ativado, o SQLite gera dois ficheiros temporários ao lado do ficheiro principal `database.db`:
1. `database.db-wal`: O log sequencial onde todas as alterações de transações confirmadas são escritas em modo append-only.
2. `database.db-shm`: Memória partilhada (*Shared Memory File*) usada como índice rápido pelos leitores para mapear as páginas mais recentes dentro do ficheiro WAL.

---

## 3. Configuração Ótima de Pragmas para o JARVIS OS

Para evitar erros de `database is locked` e garantir máxima performance sob múltiplos agentes assíncronos:

```python
import sqlite3

def get_optimized_sqlite_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
    
    # 1. Ativar modo WAL
    conn.execute("PRAGMA journal_mode = WAL;")
    
    # 2. Sincronização NORMAL (segura em WAL contra falhas de app, muito mais rápida que FULL)
    conn.execute("PRAGMA synchronous = NORMAL;")
    
    # 3. Timeout de espera de bloqueio de 10 segundos antes de lançar BusyError
    conn.execute("PRAGMA busy_timeout = 10000;")
    
    # 4. Aumentar cache em memória (64MB)
    conn.execute("PRAGMA cache_size = -64000;")
    
    # 5. Enforce de Chaves Estrangeiras
    conn.execute("PRAGMA foreign_keys = ON;")
    
    return conn
```

---

## 4. O Processo de Checkpoint (WAL $\rightarrow$ DB)
À medida que o ficheiro `-wal` cresce, o SQLite transfere periodicamente as páginas alteradas de volta para o ficheiro `.db` principal. Por defeito, um checkpoint passivo é disparado quando o WAL atinge 1000 páginas (~4MB).

Se o processo fechar inesperadamente, o SQLite executa auto-recovery no próximo `connect()` aplicando o WAL restante sem perda de dados (ACID completo).

---

## 5. Common Failure Modes
- **Leitor Aberto Infinito (Starvation de Checkpoint)**: Se uma conexão de leitura esquecer um cursor aberto numa transação antiga, o SQLite não consegue truncar o ficheiro WAL, fazendo o `-wal` crescer para centenas de megabytes.
- **Rede / Pastas Partilhadas (NFS/SMB)**: O modo WAL requer memória partilhada POSIX (`shm`), falhando categoricamente em pastas partilhadas de rede.

---

## 6. Related Concepts
- [[Optimistic vs Pessimistic Locking]]
- [[Database Crash Consistency and Recovery]]
- [[How to Diagnose and Resolve SQLite Database Locked Errors]]
- [[Idempotency in Software Systems]]

---

## 7. Sources
- *SQLite Official Documentation - Write-Ahead Logging*: https://www.sqlite.org/wal.html
- *SQLite Pragmas Specification*: https://www.sqlite.org/pragma.html
