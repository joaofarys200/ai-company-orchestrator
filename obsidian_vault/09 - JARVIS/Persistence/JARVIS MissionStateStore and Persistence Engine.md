---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
difficulty: advanced
tags:
  - jarvis
  - persistence
  - state-store
  - sqlite
  - mission-state
prerequisites:
  - "[[SQLite WAL Mode and Concurrency]]"
  - "[[Database Crash Consistency and Recovery]]"
related:
  - "[[JARVIS State Store and Persistence]]"
  - "[[JARVIS MissionExecutorService and Autonomy Controller]]"
  - "[[How to Diagnose and Resolve SQLite Database Locked Errors]]"
used_by:
  - "[[JARVIS System Architecture]]"
failure_modes:
  - "[[Lesson - SQLite Lock Starvation from Unclosed Readers]]"
implementation:
  - "[[JARVIS State Store and Persistence]]"
sources:
  - title: JARVIS Codebase - agents/mission_state.py and database.py
    type: JARVIS_INTERNAL
    url: internal://agents/mission_state.py
---

# 🗄️ JARVIS MissionStateStore and Persistence Engine

## 1. Purpose
O `MissionStateStore` é o subsistema de persistência de estado do JARVIS OS responsável por armazenar, sincronizar e recuperar o progresso, histórico de checkpoints, saídas de passos e metadados de missões autónomas.

---

## 2. Responsibilities
- Manter o grafo de execução de passos e tarefas serializado no SQLite local.
- Fornecer transações atómicas para transição de estados (`PENDING` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `COMPLETED` / `FAILED`).
- Gerir checkpoints binários e snapshots incrementais de workspace.
- Fornecer leitura não-bloqueante para o despachante de telemetria WebSocket.

---

## 3. Inputs & Outputs
- **Inputs**: Objetos de estado de missão (`MissionState`), eventos de transição de passo, payloads de saída de ferramentas.
- **Outputs**: Registos persistidos em SQLite, snapshots JSON de recuperação pós-crash, telemetria estruturada.

---

## 4. State Management & Invariants
- O estado reside em `database.db` com `PRAGMA journal_mode = WAL`.
- Toda a transição de status requer gravação atómica na tabela `missions` e `steps`.

---

## 5. Dependencies
- [`database.py`](file:///c:/Users/joaor/Desktop/JarvisOS/database.py): Conexão e pool de SQLite com pragmas WAL.
- [`agents/mission_state.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/mission_state.py): Modelos Pydantic de estado e serialização.

---

## 6. Failure Modes & Recovery
- **Failure**: `database is locked` por concorrência de múltiplos leitores ou checkpoints bloqueados.
- **Recovery**: `PRAGMA busy_timeout = 15000;`, context managers estritos `with conn:`, e checkpoint manual via background worker (ver [[Lesson - SQLite Lock Starvation from Unclosed Readers]]).

---

## 7. Security Boundaries
- O ficheiro `database.db` é protegido com permissões restritas no host e nunca é exposto diretamente a comandos executados na sandbox.

---

## 8. Evidence Produced & Tests
- **Evidence**: Tabela `missions`, tabela `steps`, registos em `telemetry_logs`.
- **Tests**: `tests/test_mission_state.py`, `tests/test_git_checkpoint_bytes.py`.

---

## 9. Related Components
- [[JARVIS Component Architecture]]
- [[JARVIS MissionExecutorService and Autonomy Controller]]
- [[JARVIS MissionRecoveryWatchdog and Crash Recovery]]
