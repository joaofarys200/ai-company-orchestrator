---
type: concept
domain: backend-systems
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - backend
  - distributed-systems
  - distributed-locks
  - fencing-tokens
  - redlock
prerequisites:
  - "[[Optimistic vs Pessimistic Locking]]"
  - "[[Consensus and Raft Protocol]]"
related:
  - "[[SQLite WAL Mode and Concurrency]]"
  - "[[Database Crash Consistency and Recovery]]"
  - "[[Distributed Transactions and Saga Pattern]]"
used_by:
  - "[[JARVIS State Store and Persistence]]"
failure_modes:
  - "[[Lesson - SQLite Lock Starvation from Unclosed Readers]]"
implementation:
  - "[[JARVIS System Architecture]]"
sources:
  - title: How to do distributed locking (Martin Kleppmann)
    type: PRIMARY_SOURCE
    url: https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
---

# 🔒 Distributed Locks and Fencing Tokens

## 1. Pergunta Central
> *Como impedir que dois processos distribuídos escrevam simultaneamente no mesmo recurso compartilhado quando pausas de Garbage Collection ou atrasos de rede fazem um processo acreditar que ainda possui o lock expirado?*

---

## 2. A Falha Clássica dos Locks Baseados em Tempo (Lease Expiration Bug)

```
Processo A                           Servidor de Lock (Redis/ZooKeeper)                   Storage / DB
    |                                                 |                                         |
    | --- 1. Adquire Lock (TTL: 10s) ---------------> |                                         |
    |                                                 |                                         |
[ Pausa de GC de 15 segundos no Processo A ]          |                                         |
    |                                                 | (TTL expira aos 10s! Lock é libertado)  |
    |                                                 |                                         |
    |                     Processo B                  |                                         |
    |                         | --- 2. Adquire Lock ->|                                         |
    |                         | ------------------ 3. Escreve Dados com Sucesso --------------->| (OK!)
    |                                                                                           |
[ Processo A acorda da pausa ]                                                                  |
    | ------------------------------------ 4. Escreve Dados Achando que tem o Lock! ----------->| (CORRUPÇÃO!)
```

---

## 3. A Solução Formal: Fencing Tokens (Tokens com Barreira Monotónica)
Toda a vez que o servidor de lock concede uma concessão, ele emite um número inteiro **estritamente crescente** chamado **Fencing Token** ($Token = 1, 2, 3, \dots$).

O recurso de armazenamento final (banco de dados ou disco) rejeita qualquer escrita cujo token seja inferior ao maior token já processado:

```
Processo A (Token = 33) acorda e tenta escrever -> Storage rejeita: "Já processei Token 34 do Processo B!"
```

---

## 4. Implementação em SQL

```sql
-- O storage mantém o maior fencing token observado
UPDATE shared_storage 
SET content = :new_content, highest_token = :fencing_token
WHERE resource_id = :id AND :fencing_token > highest_token;

-- Se rows_affected == 0 -> Escrita bloqueada por token obsoleto!
```

---

## 5. Related Concepts
- [[Optimistic vs Pessimistic Locking]]
- [[Consensus and Raft Protocol]]
- [[Distributed Transactions and Saga Pattern]]
