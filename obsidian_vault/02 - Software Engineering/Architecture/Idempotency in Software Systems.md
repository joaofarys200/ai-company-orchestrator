---
type: concept
domain: software-engineering
difficulty: intermediate
tags:
  - software-engineering
  - idempotency
  - distributed-systems
  - reliability
  - api-design
status: verified
---

# 🔁 Idempotency in Software Systems

## 1. Definição & Importância
Uma operação é dita **idempotente** se a sua execução repetida $N$ vezes ($N \ge 1$) com os mesmos parâmetros produz exatamente o mesmo resultado e o mesmo estado final no sistema que uma única execução.

$$\forall x, \quad f(f(x)) = f(x)$$

Em arquiteturas agênticas e sistemas distribuídos sujeitos a retentativas de rede, timeouts e falhas transitórias de conexão, a idempotência é o único mecanismo formal que garante que retentativas não causem cobranças duplicadas, criação de registos duplicados ou modificações de ficheiros inconsistentes.

---

## 2. Padrão de Chave de Idempotência (Idempotency Key Pattern)

```
Client / Agent                                          Server / Service
      |                                                        |
      | ---- POST /api/tasks (Idempotency-Key: "uuid-123") --> |
      |                                                        | --- [ Verifica se "uuid-123" existe ]
      |                                                        |     (Não existe -> Executa & Salva Resultado)
      | <--- 200 OK (Task ID: 456, Status: CREATED) ---------- |
      |                                                        |
  (Timeout de Rede / Perda de ACK pelo cliente)                |
      |                                                        |
      | ---- POST /api/tasks (Idempotency-Key: "uuid-123") --> |
      |                                                        | --- [ Verifica se "uuid-123" existe ]
      |                                                        |     (Existe! Retorna resultado em cache)
      | <--- 200 OK (Task ID: 456, Status: CREATED) ---------- |
```

---

## 3. Implementação de Decorator de Idempotência em Python

```python
import sqlite3
import json
from typing import Callable, Any

def idempotent_operation(db_conn: sqlite3.Connection):
    def decorator(func: Callable):
        async def wrapper(*args, idempotency_key: str, **kwargs) -> Any:
            cursor = db_conn.cursor()
            
            # 1. Verificar se a chave já foi processada
            cursor.execute(
                "SELECT response_json FROM idempotency_keys WHERE key = ?", 
                (idempotency_key,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            
            # 2. Executar a operação real
            result = await func(*args, **kwargs)
            
            # 3. Armazenar resultado atomicamente
            cursor.execute(
                "INSERT INTO idempotency_keys (key, response_json, created_at) VALUES (?, ?, datetime('now'))",
                (idempotency_key, json.dumps(result))
            )
            db_conn.commit()
            return result
        return wrapper
    return decorator
```

---

## 4. Idempotência em Modificação de Ficheiros
- **Anti-Padrão Não-Idempotente**: Adicionar uma linha ao fim do ficheiro (`f.write("import foo\n")`). Se o agente retentar, haverá 5 imports duplicados.
- **Padrão Idempotente**: Verificar se a linha/símbolo já existe no AST antes de inserir, ou substituir o bloco inteiro com base em hashes.

---

## 5. Related Concepts
- [[Distributed Transactions and Saga Pattern]]
- [[Model Harness Architecture]]
- [[Safe Rollback and Git Transactional Strategies]]
- [[SQLite WAL Mode and Concurrency]]

---

## 6. Sources
- *IETF Draft - The Idempotency-Key HTTP Header Field*: https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-04
- *Stripe Engineering - Designing robust and predictable APIs with idempotency*: https://stripe.com/blog/idempotency
