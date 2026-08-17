---
type: comparison
domain: backend-systems
difficulty: intermediate
tags:
  - backend
  - databases
  - concurrency
  - locking
  - transactions
status: verified
---

# ⚖️ Optimistic vs Pessimistic Locking

## 1. Tabela Comparativa

| Dimensão | Bloqueio Otimista (Optimistic Locking) | Bloqueio Pessimista (Pessimistic Locking) |
|---|---|---|
| **Premissa Fundamental** | Conflitos são raros; valida no momento do commit | Conflitos são frequentes; bloqueia o registo na leitura |
| **Mecanismo de Implementação** | Coluna de versão (`version INT` ou `updated_at`) | `SELECT ... FOR UPDATE` ou exclusão a nível de linha/tabela |
| **Impacto na Concorrência** | Altíssimo rendimento (*throughput*); sem deadlocks de BD | Baixo rendimento sob carga; alto risco de contenção e deadlocks |
| **Tratamento de Colisão** | A escrita falha silenciosamente ou lança erro de concorrência que exige retry na aplicação | As outras transações ficam bloqueadas em fila aguardando liberação |
| **Adequação para Agentes de IA** | Excelente para estados de missões e edição de ficheiros assíncrona | Adequado apenas para débitos financeiros em tempo real e reservas atómicas |

---

## 2. Padrão de Bloqueio Otimista com Coluna de Versão

```sql
-- 1. Leitura do estado atual da missão
SELECT id, status, version FROM missions WHERE id = 'task-102';
-- Retorna: version = 3

-- 2. Agente processa a alteração (durante 5 segundos)...

-- 3. Tentativa de Atualização Condicional Atómica
UPDATE missions 
SET status = 'COMPLETED', version = version + 1 
WHERE id = 'task-102' AND version = 3;

-- 4. Verificação de Linhas Afetadas:
-- Se rows_affected == 1 -> Sucesso!
-- Se rows_affected == 0 -> Conflito de concorrência detectado! Outro agente alterou o registo.
```

---

## 3. Implementação em Python com Retry Loop

```python
import sqlite3

class ConcurrencyConflictError(Exception):
    pass

def update_mission_status_optimistic(conn: sqlite3.Connection, mission_id: str, new_status: str, max_retries: int = 3):
    for attempt in range(max_retries):
        cursor = conn.cursor()
        cursor.execute("SELECT status, version FROM missions WHERE id = ?", (mission_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Missão inexistente")
            
        current_status, current_version = row
        
        # Executar update atómico
        cursor.execute(
            "UPDATE missions SET status = ?, version = version + 1 WHERE id = ? AND version = ?",
            (new_status, mission_id, current_version)
        )
        conn.commit()
        
        if cursor.rowcount == 1:
            return True  # Atualizado com sucesso
            
    raise ConcurrencyConflictError(f"Falha ao atualizar missão {mission_id} após {max_retries} colisões.")
```

---

## 4. Related Concepts
- [[SQLite WAL Mode and Concurrency]]
- [[Database Crash Consistency and Recovery]]
- [[Distributed Transactions and Saga Pattern]]
- [[Idempotency in Software Systems]]

---

## 5. Sources
- *Martin Fowler - Patterns of Enterprise Application Architecture (Optimistic Offline Lock)*
- *PostgreSQL Concurrency Control Documentation*: https://www.postgresql.org/docs/current/mvcc.html
