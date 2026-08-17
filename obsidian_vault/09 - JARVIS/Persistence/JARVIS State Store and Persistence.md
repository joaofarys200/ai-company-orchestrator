---
type: concept
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - persistence
  - sqlite
  - state-store
  - database
status: verified
---

# 🗄️ JARVIS State Store and Persistence

## 1. Arquitetura de Armazenamento Local
O **JARVIS OS** adota persistência estritamente local baseada em **SQLite** configurado com modo **Write-Ahead Logging (WAL)** no ficheiro [`database.db`](file:///c:/Users/joaor/Desktop/JarvisOS/database.py).

---

## 2. Tabelas Principais do Schema (`database.py`)

1. **`missions`**: Armazena o identificador, título, status (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`), progresso e checkpoints serializados em JSON.
2. **`tasks` / `steps`**: Tarefas individuais decompostas pelo agente Planner com dependências de DAG.
3. **`telemetry_logs`**: Registo temporal de mensagens, eventos de sistema, saída de ferramentas e uso de tokens.
4. **`idempotency_keys`**: Chaves únicas para garantir que comandos repetidos não executem efeitos colaterais duplicados.

---

## 3. Resiliência e Prevenção de Bloqueios
- `PRAGMA journal_mode = WAL;`
- `PRAGMA busy_timeout = 10000;` (10 segundos de espera para resolver concorrência de múltiplos agentes)
- `PRAGMA synchronous = NORMAL;`

---

## 4. Related Concepts
- [[SQLite WAL Mode and Concurrency]]
- [[Database Crash Consistency and Recovery]]
- [[How to Diagnose and Resolve SQLite Database Locked Errors]]
- [[JARVIS Component Architecture]]

---

## 5. Sources
- *JARVIS OS Codebase — `database.py`, `setup_db.py`*
