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
  - distributed-locks
  - fencing-tokens
  - deadlock-resolution
prerequisites:
  - "[[Distributed Locks and Fencing Tokens]]"
  - "[[Optimistic vs Pessimistic Locking]]"
related:
  - "[[How to Recover Interrupted Background Workers]]"
  - "[[Consensus and Raft Protocol]]"
used_by:
  - "[[JARVIS MissionRecoveryWatchdog and Crash Recovery]]"
failure_modes:
  - "[[Lesson - SQLite Lock Starvation from Unclosed Readers]]"
implementation:
  - "[[JARVIS MissionRecoveryWatchdog and Crash Recovery]]"
sources:
  - title: Martin Kleppmann - How to do distributed locking
    type: PRIMARY_SOURCE
    url: https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
---

# 🛠️ï¸ Runbook - How to Resolve Stale Distributed Locks and Fencing Collisions

## 1. Critérios de Sucesso e Falha
- **Critério de Sucesso**: O lock obsoleto é libertado, o token de barreira (*Fencing Token*) é incrementado monotonicamente e a nova tarefa assume a posse exclusiva do recurso sem corrupção de estado.
- **Critério de Falha**: Dois nós concorrentes continuam a tentar escrever com o mesmo fencing token expirado gerando split-brain.

---

## 2. Diagnóstico de Colisão
1. Inspecionar logs procurando por: `FENCING_COLLISION: Stale token N rejected by storage layer`.
2. Verificar se o worker original que detinha o lock está bloqueado em pausa de GC ou desconectado.

---

## 3. Procedimento Operacional de Resolução

### Passo 1: Invalidar o Lock Antigo no Servidor de Coordenação
```python
def force_release_stale_lock(lock_key: str, last_owner_id: str):
    current_owner = redis_client.get(f"lock:{lock_key}")
    if current_owner == last_owner_id:
        redis_client.delete(f"lock:{lock_key}")
        print(f"[Lock Resolution] Lock obsoleto {lock_key} removido.")
```

### Passo 2: Emitir Novo Fencing Token Monotónico
```python
def acquire_fenced_lock(lock_key: str, new_owner_id: str) -> int:
    # 1. Incrementar contador atómico global
    fencing_token = redis_client.incr(f"fencing_counter:{lock_key}")
    
    # 2. Adquirir lock com lease TTL
    acquired = redis_client.set(f"lock:{lock_key}", new_owner_id, nx=True, ex=30)
    if not acquired:
        raise TimeoutError("Não foi possível adquirir lock concorrente.")
        
    return fencing_token
```

### Passo 3: Reexecutar Escrita com Novo Token
O storage aceita a nova escrita porque `new_token > previous_highest_token`.

---

## 4. Related Concepts
- [[Distributed Locks and Fencing Tokens]]
- [[Optimistic vs Pessimistic Locking]]
- [[Consensus and Raft Protocol]]

