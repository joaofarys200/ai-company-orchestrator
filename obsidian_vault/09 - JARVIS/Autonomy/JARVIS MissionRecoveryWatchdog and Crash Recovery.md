---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
difficulty: advanced
tags:
  - jarvis
  - reliability
  - watchdog
  - crash-recovery
  - checkpoints
prerequisites:
  - "[[Database Crash Consistency and Recovery]]"
  - "[[JARVIS MissionStateStore and Persistence Engine]]"
related:
  - "[[How to Recover Interrupted Background Workers]]"
  - "[[JARVIS MissionExecutorService and Autonomy Controller]]"
used_by:
  - "[[JARVIS System Architecture]]"
failure_modes:
  - "[[Lesson - SQLite Lock Starvation from Unclosed Readers]]"
implementation:
  - "[[JARVIS Mission State Machine and Autonomy]]"
sources:
  - title: JARVIS Codebase - agents/mission_autonomy.py (Recovery Watchdog)
    type: JARVIS_INTERNAL
    url: internal://agents/mission_autonomy.py
---

# ðŸ›°ï¸ JARVIS MissionRecoveryWatchdog and Crash Recovery

## 1. Purpose
O `MissionRecoveryWatchdog` Ã© o processo em segundo plano responsÃ¡vel por detetar interrupÃ§Ãµes inesperadas de processos, tarefas zumbis e falhas de energia do anfitriÃ£o, recuperando o estado consistente da missÃ£o a partir do Ãºltimo checkpoint.

---

## 2. Responsibilities
- Monitorizar batimentos cardÃ­acos (*Heartbeats*) dos workers e agentes em execuÃ§Ã£o.
- Identificar missÃµes que permaneceram no estado `IN_PROGRESS` sem atividade recente ($Heartbeat\_Age > 60\text{s}$).
- Restaurar a Ã¡rvore de ficheiros da sandbox a partir do snapshot Git transacional mais recente.
- Transitar a missÃ£o para o estado `PAUSED_RECOVERED` ou reiniciar o passo falhado de forma idempotente.

---

## 3. Inputs & Outputs
- **Inputs**: Tabela `missions` e `steps` com status `IN_PROGRESS`, timestamps de heartbeat.
- **Outputs**: ReversÃ£o da sandbox via `git reset --hard <checkpoint_hash>`, emissÃ£o de evento de recuperaÃ§Ã£o.

---

## 4. State Management & Invariants
- Nenhuma tarefa interrompida pode retomar a execuÃ§Ã£o sem antes validar a integridade dos ficheiros em disco contra o hash SHA-256 do checkpoint.

---

## 5. Dependencies
- [`agents/mission_autonomy.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/mission_autonomy.py)
- [`agents/patch_engine.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/patch_engine.py)
- [`database.py`](file:///c:/Users/joaor/Desktop/JarvisOS/database.py)

---

## 6. Failure Modes & Recovery
- **Failure**: Snapshot corrompido ou banco de dados bloqueado durante o processo de recuperaÃ§Ã£o.
- **Recovery**: ReversÃ£o para o commit inicial da missÃ£o e emissÃ£o de alerta sonoro via `voice_service.py`.

---

## 7. Security Boundaries
- A restauraÃ§Ã£o de ficheiros opera exclusivamente dentro de `sandbox_dir/` e nunca toca em ficheiros de configuraÃ§Ã£o fora do projeto.

---

## 8. Evidence Produced & Tests
- **Evidence**: Registos em `telemetry_logs` com categoria `CRASH_RECOVERY_ATTEMPT`.
- **Tests**: `tests/test_mission_autonomy.py::test_watchdog_recovers_orphaned_task`.

---

## 9. Related Concepts
- [[How to Recover Interrupted Background Workers]]
- [[Database Crash Consistency and Recovery]]
- [[Safe Rollback and Git Transactional Strategies]]

