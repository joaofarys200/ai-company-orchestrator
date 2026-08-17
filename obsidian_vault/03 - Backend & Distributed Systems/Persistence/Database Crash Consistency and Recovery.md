---
type: concept
domain: backend-systems
difficulty: intermediate
tags:
  - backend
  - databases
  - crash-recovery
  - acid
  - consistency
status: verified
---

# 🛡️ Database Crash Consistency and Recovery

## 1. Princípios ACID e o Desafio da Queda Abrupta
Quando o processo anfitrião de um agente ou o sistema operacional desliga abruptamente (ex: corte de energia, `kill -9`, kernel panic), a integridade dos dados no disco depende de mecanismos de **Crash Consistency**:
- **Atomicidade (Atomicity)**: Todas as alterações de uma transação ocorrem no disco ou nenhuma ocorre.
- **Durabilidade (Durability)**: Uma vez confirmada a transação (`COMMIT`), os dados sobrevivem a falhas imediatas de energia.

```
Memória Volátil (RAM):                Disco Persistente (Storage):
+-------------------------+          +------------------------------+
| Buffer Pool / Caches    | --- Flush/fsync ---> | Master Database File (.db)   |
| Dirty Pages             |          | Write-Ahead Log (.db-wal)    |
+-------------------------+          +------------------------------+
```

---

## 2. A Chamada de Sistema `fsync` e Barreiras de Escrita
Escrever com `file.write()` apenas transfere os dados para o buffer do sistema operacional na memória RAM (*Page Cache*). Para garantir durabilidade física no disco magnético ou NVMe, o motor de base de dados emite a chamada de sistema **`fsync`** (ou `FlushFileBuffers` no Windows).

---

## 3. Padrão de Recuperação de Estado com Checkpointing

```python
import sqlite3
import json

def restore_agent_mission_state(db_conn: sqlite3.Connection, mission_id: str) -> dict:
    """
    Recupera o último estado consistente da missão após crash do worker.
    """
    cursor = db_conn.cursor()
    cursor.execute(
        """
        SELECT last_checkpoint_json, status 
        FROM missions 
        WHERE id = ?
        """,
        (mission_id,)
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Missão {mission_id} não encontrada.")

    checkpoint_data, status = row
    if status == "IN_PROGRESS":
        # Marcar como recuperada para evitar duplicação cega
        cursor.execute("UPDATE missions SET status = 'RECOVERED_AFTER_CRASH' WHERE id = ?", (mission_id,))
        db_conn.commit()

    return json.loads(checkpoint_data)
```

---

## 4. Related Concepts
- [[SQLite WAL Mode and Concurrency]]
- [[Optimistic vs Pessimistic Locking]]
- [[Distributed Transactions and Saga Pattern]]
- [[How to Recover Interrupted Background Workers]]

---

## 5. Sources
- *Designing Data-Intensive Applications (DDIA - Martin Kleppmann, Chapter 7: Transactions)*
- *SQLite Crash Recovery Mechanics*: https://www.sqlite.org/atomiccommit.html
