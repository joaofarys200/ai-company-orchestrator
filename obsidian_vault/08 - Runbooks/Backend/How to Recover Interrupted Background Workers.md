---
type: troubleshooting
domain: backend-systems
difficulty: intermediate
tags:
  - backend
  - troubleshooting
  - workers
  - background-tasks
  - recovery
status: verified
---

# 🛠️ How to Recover Interrupted Background Workers

## 1. Sintomas & Cenário de Falha
- Um agente ou worker de background foi terminado no meio de uma tarefa por reinicialização do servidor, exceção não tratada ou timeout.
- A base de dados mantém a tarefa com `status = "IN_PROGRESS"`, mas não existe nenhum processo ativo a processá-la (estado órfão/zumbi).

---

## 2. Diagnóstico de Tarefas Órfãs

```sql
-- Identificar tarefas marcadas como IN_PROGRESS cujo heartbeat expirou há mais de 5 minutos
SELECT id, title, agent_name, last_heartbeat_at 
FROM missions 
WHERE status = 'IN_PROGRESS' 
  AND last_heartbeat_at < datetime('now', '-5 minutes');
```

---

## 3. Protocolo de Auto-Recuperação (Watchdog Runbook)

```
[ Watchdog Timer Dispara a cada 60s ]
                  |
                  v
[ Consulta Tarefas 'IN_PROGRESS' com Heartbeat Vencido ]
                  |
        +---------+---------+
        |                   |
  (Nenhuma Órfã)       (Encontradas Órfãs)
        |                   |
        v                   v
     (Dorme)    [ Para cada tarefa órfã ]:
                1. Marcar status = "CRASH_RECOVERING"
                2. Ler último Checkpoint JSON do banco
                3. Re-enfileirar no EventBus com `attempt = attempt + 1`
                4. Se `attempt > max_retries` -> Marcar "FAILED_FATAL"
```

---

## 4. Implementação do Watchdog em Python

```python
import sqlite3
import datetime
import json

def recover_abandoned_tasks(db_path: str, max_retries: int = 3):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, payload_json, retry_count 
            FROM background_tasks 
            WHERE status = 'IN_PROGRESS' 
              AND last_heartbeat < datetime('now', '-3 minutes')
        """)
        orphans = cursor.fetchall()
        
        for task_id, payload_json, retry_count in orphans:
            if retry_count < max_retries:
                print(f"[Watchdog] Recuperando tarefa órfã {task_id} (Tentativa {retry_count + 1})")
                cursor.execute("""
                    UPDATE background_tasks 
                    SET status = 'PENDING', 
                        retry_count = retry_count + 1,
                        last_heartbeat = datetime('now')
                    WHERE id = ?
                """, (task_id,))
            else:
                print(f"[Watchdog] Tarefa {task_id} excedeu limite de retries. Marcando como FAILED.")
                cursor.execute("UPDATE background_tasks SET status = 'FAILED' WHERE id = ?", (task_id,))
```

---

## 5. Related Concepts
- [[Database Crash Consistency and Recovery]]
- [[Distributed Transactions and Saga Pattern]]
- [[Message Queues and Event-Driven Architectures]]

---

## 6. Sources
- *Designing Data-Intensive Applications (DDIA - Martin Kleppmann)*
- *Celery Architecture Documentation - Worker Lost & Heartbeat Handling*: https://docs.celeryq.dev/en/stable/userguide/workers.html
